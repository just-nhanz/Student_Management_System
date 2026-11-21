from datetime import date, datetime

import pymysql

from app.config import Config, ROLE_STUDENT, ROLE_TRAINING
from app.repositories.account_repo import AccountRepo
from app.repositories.audit_repo import AuditRepo
from app.repositories.catalog_repo import CatalogRepo
from app.repositories.course_repo import CourseRepo
from app.repositories.enroll_repo import EnrollRepo
from app.repositories.grade_repo import GradeRepo
from app.repositories.payment_repo import PaymentRepo
from app.repositories.user_repo import UserRepo
from app.services import ServiceError, require_role, validation_error
from app.services.fee_service import FeeService
from app.utils.database import Database


def current_semester_id(catalog):
    """Hoc ky hien tai = hoc ky chua ngay hom nay; neu khong co thi lay hoc ky moi nhat."""
    today = date.today()
    semesters = catalog.list_semesters()
    for sem in semesters:
        if sem["start_date"] <= today <= sem["end_date"]:
            return sem["semester_id"]
    if len(semesters) > 0:
        return semesters[0]["semester_id"]
    return None


def periods_overlap(a_start, a_count, b_start, b_count):
    return a_start <= b_start + b_count - 1 and b_start <= a_start + a_count - 1


class EnrollService:
    """UC08-UC13: mo lop hoc phan, phan cong giang vien, dang ky / huy mon, thoi khoa bieu, bang diem."""

    def __init__(self, connection=None):
        self.connection = connection
        self.fees = FeeService(connection)

    def _db(self):
        return Database(self.connection)

    # ------------------------------------------------------------------ UC08
    def open_section(self, actor, subject_id, semester_id, classroom, day_of_week, start_period, period_count,
                     max_capacity, ip=None):
        require_role(actor, ROLE_TRAINING)
        errors = {}
        try:
            day_of_week = int(day_of_week)
            start_period = int(start_period)
            period_count = int(period_count)
            max_capacity = int(max_capacity)
        except (TypeError, ValueError):
            raise validation_error({"schedule": "Day, periods and capacity must be numbers."})
        if (classroom or "").strip() == "":
            errors["classroom"] = "Required."
        if not 2 <= day_of_week <= 8:
            errors["day_of_week"] = "Must be 2-8."
        if not 1 <= start_period <= 12 or period_count < 1 or start_period + period_count - 1 > 12:
            errors["periods"] = "Periods must lie within 1-12."
        if max_capacity <= 0:
            errors["max_capacity"] = "Must be greater than 0."   # UC08.3
        if errors:
            raise validation_error(errors)
        with self._db() as db:
            catalog = CatalogRepo(db)
            courses = CourseRepo(db)
            subject = catalog.find_subject(subject_id or "")
            semester = catalog.find_semester(semester_id or "")
            # UC08.2.2: mon hoc ngung hoat dong / hoc ky khong hop le thi tu choi
            if subject is None or semester is None:
                raise ServiceError("The subject or the semester does not exist.")
            if subject["status"] != "ACTIVE":
                raise ServiceError("The subject is discontinued and cannot be opened.")
            end_period = start_period + period_count - 1
            # UC08.2.2: trung phong / trung lich
            conflict = courses.find_room_conflict(semester_id, classroom.strip(), day_of_week, start_period, end_period)
            if conflict is not None:
                raise ServiceError("Room conflict with section %s. Please choose another room or time."
                                   % conflict["course_section_id"])
            section_no = courses.next_section_no(subject_id, semester_id)
            section_id = "%s-%s-%02d" % (subject_id, semester_id, section_no)
            courses.insert_section(section_id, subject_id, semester_id, section_no, classroom.strip(), day_of_week,
                                   start_period, period_count, max_capacity)
            AuditRepo(db).add(actor["account_id"], "SECTION_OPEN", "course_section", section_id, None, ip)
        return section_id

    def list_sections(self, actor, semester_id=None):
        require_role(actor, ROLE_TRAINING)
        with self._db() as db:
            semester_id = semester_id or current_semester_id(CatalogRepo(db))
            return {"semester_id": semester_id, "sections": CourseRepo(db).list_sections(semester_id)}

    # ------------------------------------------------------------------ UC09
    def assign_lecturer(self, actor, section_id, lecturer_id, confirmed=True, ip=None):
        require_role(actor, ROLE_TRAINING)
        if not confirmed:
            return False
        with self._db() as db:
            courses = CourseRepo(db)
            section = courses.find_section(section_id)
            if section is None or section["status"] != "OPEN":
                raise ServiceError("The course section does not exist or is closed.")
            lecturer = UserRepo(db).find_lecturer(lecturer_id or "")
            if lecturer is None or lecturer["employment_status"] != "ACTIVE":
                raise ServiceError("The lecturer was not found or is no longer active.")
            end_period = section["start_period"] + section["period_count"] - 1
            clash = courses.find_lecturer_conflict(lecturer_id, section["semester_id"], section["day_of_week"],
                                                   section["start_period"], end_period, section_id)
            if clash is not None:
                raise ServiceError("The lecturer has a schedule conflict with section %s." % clash["course_section_id"])
            courses.set_lecturer(section_id, lecturer_id)
            AuditRepo(db).add(actor["account_id"], "LECTURER_ASSIGN", "course_section", section_id,
                              "old=%s new=%s" % (section["lecturer_id"], lecturer_id), None if ip is None else ip)
        return True

    def remove_lecturer(self, actor, section_id, ip=None):
        """UC06: go phan cong de co the vo hieu hoa giang vien."""
        require_role(actor, ROLE_TRAINING)
        with self._db() as db:
            courses = CourseRepo(db)
            section = courses.find_section(section_id)
            if section is None:
                raise ServiceError("The course section does not exist.")
            courses.set_lecturer(section_id, None)
            AuditRepo(db).add(actor["account_id"], "LECTURER_UNASSIGN", "course_section", section_id,
                              "old=%s" % section["lecturer_id"], ip)
        return True

    # ------------------------------------------------------------------ UC10
    def list_open_sections(self, user, semester_id=None):
        require_role(user, ROLE_STUDENT)
        with self._db() as db:
            semester_id = semester_id or current_semester_id(CatalogRepo(db))
            sections = CourseRepo(db).list_open_sections(semester_id)
            for sec in sections:
                sec["remaining"] = sec["max_capacity"] - sec["enrolled"]
            return {"semester_id": semester_id, "sections": sections}

    def register(self, user, section_id, ip=None):
        """UC10: chuoi kiem tra 9 buoc (SRS 1.9) trong MOT transaction; loi dau tien dung chuoi."""
        require_role(user, ROLE_STUDENT)
        with self._db() as db:
            users = UserRepo(db)
            catalog = CatalogRepo(db)
            courses = CourseRepo(db)
            enroll = EnrollRepo(db)
            student = users.find_student_by_account(user["account_id"])
            if student is None:
                raise ServiceError("Student profile not found.")
            section = courses.find_section(section_id)
            now = datetime.now()

            # UC10 - BR-03 (buoc 1): trong thoi gian dang ky cua hoc ky
            if section is not None:
                semester = catalog.find_semester(section["semester_id"])
                if not semester["reg_start"] <= now <= semester["reg_end"]:
                    raise ServiceError("The registration period of this semester is closed.")
            # UC10 - BR-03 (buoc 2): tai khoan ACTIVE va sinh vien dang hoc
            account = AccountRepo(db).find_by_id(user["account_id"])
            if account["status"] != "ACTIVE" or student["academic_status"] != "STUDYING" \
                    or student["record_status"] != "ACTIVE":
                raise ServiceError("Your account or student status does not allow registration.")
            # UC10 - BR-03 (buoc 3): lop ton tai va dang OPEN
            if section is None:
                raise ServiceError("The course section does not exist.")
            if section["status"] != "OPEN":
                raise ServiceError("The course section is not open for registration.")
            # UC10 - BR-06, NFR-PE-05 (buoc 4): khong dang ky trung
            existing = enroll.find_registration(student["student_id"], section_id)
            if existing is not None and existing["status"] == "SUCCESSFUL":
                raise ServiceError("You have already registered for this course section.")
            # UC10 - BR-07 (buoc 5): da dat tat ca mon tien quyet
            missing = []
            for prerequisite_id in catalog.list_prerequisites(section["subject_id"]):
                if not enroll.has_passed(student["student_id"], prerequisite_id, Config.PASS_THRESHOLD):
                    missing.append(prerequisite_id)
            if len(missing) > 0:
                raise ServiceError("Prerequisite subject(s) not passed: %s." % ", ".join(missing))
            # UC10 - BR-06 (buoc 6): khong trung lich voi lop da dang ky trong hoc ky
            for other in enroll.list_student_sections(student["student_id"], section["semester_id"]):
                if other["day_of_week"] == section["day_of_week"] and periods_overlap(
                        other["start_period"], other["period_count"], section["start_period"], section["period_count"]):
                    raise ServiceError("Schedule conflict with registered section %s (%s)."
                                       % (other["course_section_id"], other["subject_name"]))
            # UC10 - BR-08 (buoc 7): no qua han vuot nguong thi bi chan dang ky
            overdue = PaymentRepo(db).sum_overdue_debt(student["student_id"], date.today())
            if overdue > Config.DEBT_THRESHOLD:
                raise ServiceError("Registration is blocked because of overdue tuition debt (%s)." % overdue)
            # UC10 - Semester.max_credits (buoc 8): gioi han tin chi moi hoc ky
            used = enroll.sum_credits(student["student_id"], section["semester_id"])
            if used + section["credits"] > semester["max_credits"]:
                raise ServiceError("The credit limit of the semester (%d) would be exceeded." % semester["max_credits"])
            # UC10 - BR-05, NFR-PE-04 (buoc 9): khoa dong lop, dem SUCCESSFUL, so voi max_capacity roi moi them
            locked = courses.find_section_for_update(section_id)
            if enroll.count_successful(section_id) >= locked["max_capacity"]:
                raise ServiceError("The course section is full: no seats remain.")
            try:
                if existing is not None:
                    enroll.reactivate(existing["registration_id"], now)  # dang ky lai lop da huy
                else:
                    enroll.insert_registration(student["student_id"], section_id, now)
            except pymysql.err.IntegrityError:
                # NFR-PE-05: rang buoc UNIQUE (student_id, course_section_id) chan dang ky trung dong thoi
                raise ServiceError("You have already registered for this course section.")
            # UC10 - BR-11: tinh lai hoc phi trong cung transaction
            self.fees.recalculate_debt(db, student["student_id"], section["semester_id"])
            AuditRepo(db).add(user["account_id"], "REGISTER", "course_section", section_id, None, ip)
        return True

    # ------------------------------------------------------------------ UC11
    def drop(self, user, section_id, confirmed=True, ip=None):
        require_role(user, ROLE_STUDENT)
        with self._db() as db:
            enroll = EnrollRepo(db)
            student = UserRepo(db).find_student_by_account(user["account_id"])
            registration = enroll.find_registration(student["student_id"], section_id) if student else None
            # UC11 - BR-04: lop phai thuoc ve sinh vien va dang hop le
            if registration is None or registration["status"] != "SUCCESSFUL":
                raise ServiceError("This registration does not exist or is no longer valid.")
            section = CourseRepo(db).find_section(section_id)
            semester = CatalogRepo(db).find_semester(section["semester_id"])
            # UC11 - BR-04: con han huy
            if datetime.now() > semester["cancel_deadline"]:
                raise ServiceError("The cancellation deadline has passed; cancellation is not possible.")
            # UC11 - BR-04: chua co diem
            if GradeRepo(db).has_grade_entered(registration["registration_id"]):
                raise ServiceError("A grade has already been entered; the registration cannot be cancelled.")
            if not confirmed:
                return False  # UC11.2.2: khong xac nhan thi giu nguyen
            enroll.cancel(registration["registration_id"], datetime.now())
            # UC11.3 / BR-11: tinh lai hoc phi (co the dan den hoan tien UC19)
            self.fees.recalculate_debt(db, student["student_id"], section["semester_id"])
            AuditRepo(db).add(user["account_id"], "DROP", "course_section", section_id, None, ip)
        return True

    # ------------------------------------------------------------------ UC12
    def view_schedule(self, user, semester_id=None):
        require_role(user, ROLE_STUDENT)
        with self._db() as db:
            catalog = CatalogRepo(db)
            student = UserRepo(db).find_student_by_account(user["account_id"])
            if semester_id and catalog.find_semester(semester_id) is None:
                raise ServiceError("Invalid semester. Please choose again.")
            semester_id = semester_id or current_semester_id(catalog)
            rows = EnrollRepo(db).list_student_sections(student["student_id"], semester_id) if semester_id else []
            return {"student": student, "semester_id": semester_id, "rows": rows,
                    "semesters": catalog.list_semesters()}

    # ------------------------------------------------------------------ UC13
    def view_grades(self, user, semester_id=None):
        """UC13 - BR-10: chi hien diem cua lop co grade_status = PUBLISHED."""
        require_role(user, ROLE_STUDENT)
        with self._db() as db:
            catalog = CatalogRepo(db)
            student = UserRepo(db).find_student_by_account(user["account_id"])
            if semester_id and catalog.find_semester(semester_id) is None:
                raise ServiceError("Invalid semester. Please choose again.")
            rows = GradeRepo(db).list_published_for_student(student["student_id"], semester_id or None)
            for row in rows:
                if row["final_score"] is None:
                    row["result"] = "-"
                elif row["final_score"] >= Config.PASS_THRESHOLD:
                    row["result"] = "PASSED"
                else:
                    row["result"] = "FAILED"
            return {"student": student, "rows": rows, "semesters": catalog.list_semesters()}