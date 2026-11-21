from app.config import Config, ROLE_LECTURER, ROLE_TRAINING
from app.repositories.audit_repo import AuditRepo
from app.repositories.catalog_repo import CatalogRepo
from app.repositories.course_repo import CourseRepo
from app.repositories.enroll_repo import EnrollRepo
from app.repositories.grade_repo import GradeRepo
from app.repositories.user_repo import UserRepo
from app.services import PermissionDenied, ServiceError, page_info, require_role, validation_error
from app.services.enroll_service import current_semester_id
from app.utils.database import Database


def letter_for(final_score):
    """UC22.3: quy doi diem chu theo thang diem cau hinh duoc (Config.LETTER_SCALE)."""
    if final_score is None:
        return None
    for minimum, letter in Config.LETTER_SCALE:
        if final_score >= minimum:
            return letter
    return "F"


def parse_score(text):
    """Tra ve (gia tri hoac None, loi hoac None). Diem phai la so tu 0 den 10 (BR-09)."""
    if text is None or str(text).strip() == "":
        return None, None
    try:
        value = float(str(text).strip())
    except ValueError:
        return None, "Score must be a number."
    if value < 0 or value > 10:
        return None, "Score must be between 0 and 10."
    return round(value, 2), None


class GradeService:
    """UC20-UC22 (giang vien) va khoa / cong bo / mo khoa diem (UC08, BR-10)."""

    def __init__(self, connection=None):
        self.connection = connection

    def _db(self):
        return Database(self.connection)

    def _own_section(self, db, user, section_id):
        """BR-09 / NFR-SE-02: giang vien chi thao tac lop duoc phan cong cho minh."""
        lecturer = UserRepo(db).find_lecturer_by_account(user["account_id"])
        section = CourseRepo(db).find_section(section_id)
        if lecturer is None or section is None or section["lecturer_id"] != lecturer["lecturer_id"]:
            raise PermissionDenied("This course section is not assigned to you.")
        return lecturer, section

    # ------------------------------------------------------------------ UC20
    def teaching_schedule(self, user, semester_id=None):
        require_role(user, ROLE_LECTURER)
        with self._db() as db:
            catalog = CatalogRepo(db)
            lecturer = UserRepo(db).find_lecturer_by_account(user["account_id"])
            if semester_id and catalog.find_semester(semester_id) is None:
                raise ServiceError("Invalid semester. Please choose again.")
            semester_id = semester_id or current_semester_id(catalog)
            sections = CourseRepo(db).list_by_lecturer(lecturer["lecturer_id"], semester_id) if semester_id else []
            return {"semester_id": semester_id, "sections": sections, "semesters": catalog.list_semesters()}

    # ------------------------------------------------------------------ UC21
    def class_list(self, user, section_id, page=1):
        require_role(user, ROLE_LECTURER)
        with self._db() as db:
            lecturer, section = self._own_section(db, user, section_id)
            enroll = EnrollRepo(db)
            info = page_info(enroll.count_successful(section_id), page)
            info["rows"] = enroll.list_class(section_id, info["offset"], info["limit"])
            info["section"] = section
            return info

    # ------------------------------------------------------------------ UC22
    def grade_sheet(self, user, section_id):
        require_role(user, ROLE_LECTURER)
        with self._db() as db:
            lecturer, section = self._own_section(db, user, section_id)
            rows = GradeRepo(db).list_sheet(section_id)
            return {"section": section, "rows": rows, "read_only": section["grade_status"] != "UNLOCKED"}

    def save_sheet(self, user, section_id, entries, ip=None):
        """entries: list dict {registration_id, process_score, exam_score, version, reason}."""
        require_role(user, ROLE_LECTURER)
        with self._db() as db:
            lecturer, section = self._own_section(db, user, section_id)
            # UC22 - BR-09: chi sua duoc khi grade_status = UNLOCKED
            if section["grade_status"] != "UNLOCKED":
                raise ServiceError("The grade sheet is read-only. The Academic Manager must unlock it first (UC08).")
            grades = GradeRepo(db)
            enroll = EnrollRepo(db)
            plan = []
            errors = {}
            for entry in entries:
                reg_id = int(entry["registration_id"])
                registration = enroll.find_registration_by_id(reg_id)
                if registration is None or registration["course_section_id"] != section_id \
                        or registration["status"] != "SUCCESSFUL":
                    raise ServiceError("Registration %s does not belong to this section." % reg_id)
                process, error1 = parse_score(entry.get("process_score"))
                exam, error2 = parse_score(entry.get("exam_score"))
                if error1 or error2:
                    # UC22.2.2: diem khong hop le -> khong luu bang diem
                    errors["row %s" % registration["student_id"]] = error1 or error2
                    continue
                old = grades.find_grade(reg_id)
                old_process = float(old["process_score"]) if old and old["process_score"] is not None else None
                old_exam = float(old["exam_score"]) if old and old["exam_score"] is not None else None
                if old is not None and old_process == process and old_exam == exam:
                    continue  # khong thay doi
                had_score = old_process is not None or old_exam is not None
                reason = (entry.get("reason") or "").strip()
                # UC22 - BR-09: sua diem da co bat buoc co ly do
                if had_score and reason == "":
                    errors["row %s" % registration["student_id"]] = "A reason is required to change an existing score."
                    continue
                plan.append((reg_id, registration["student_id"], old, old_process, old_exam, process, exam,
                             reason, entry.get("version")))
            if errors:
                raise validation_error(errors)

            saved = 0
            for reg_id, student_id, old, old_process, old_exam, process, exam, reason, version in plan:
                if old is None:
                    grades.insert_grade(reg_id, process, exam, user["account_id"])
                else:
                    # UC22 / NFR-PE-06: khoa lac quan bang cot version
                    if version is None or int(version) != old["version"] or \
                            grades.update_grade(old["grade_id"], process, exam, old["version"], user["account_id"]) == 0:
                        raise ServiceError("Another user changed the grade of student %s. Please reload the sheet."
                                           % student_id)
                fresh = grades.find_grade(reg_id)
                grades.set_letter_grade(fresh["grade_id"], letter_for(fresh["final_score"]))
                # BR-13: ghi cu - moi - ly do - nguoi sua vao audit_log
                AuditRepo(db).add(user["account_id"], "GRADE_UPDATE", "grade", str(reg_id),
                                  "old=(%s,%s) new=(%s,%s) reason=%s" % (old_process, old_exam, process, exam, reason),
                                  ip)
                saved += 1
        return saved

    # ------------------------------------------------------------------ UC08: khoa / cong bo / mo khoa
    def completeness(self, actor, section_id):
        require_role(actor, ROLE_TRAINING)
        with self._db() as db:
            section = CourseRepo(db).find_section(section_id)
            if section is None:
                raise ServiceError("The course section does not exist.")
            registered, complete = GradeRepo(db).count_registered_and_complete(section_id)
            return {"section": section, "registered": registered, "complete": complete}

    def lock_grades(self, actor, section_id, confirmed=True, ip=None):
        require_role(actor, ROLE_TRAINING)
        if not confirmed:
            return False
        with self._db() as db:
            courses = CourseRepo(db)
            section = courses.find_section(section_id)
            if section is None:
                raise ServiceError("The course section does not exist.")
            if section["grade_status"] != "UNLOCKED":
                raise ServiceError("Only an Unlocked grade sheet can be locked.")
            # UC08.2.2: con sinh vien chua co diem tong ket -> tu choi va liet ke
            missing = GradeRepo(db).list_incomplete(section_id)
            if len(missing) > 0:
                names = []
                for row in missing:
                    names.append("%s (%s)" % (row["student_id"], row["full_name"]))
                raise ServiceError("Cannot lock: these students have no final score - " + ", ".join(names))
            courses.set_grade_status(section_id, "LOCKED")
            AuditRepo(db).add(actor["account_id"], "GRADE_LOCK", "course_section", section_id, "UNLOCKED->LOCKED", ip)
        return True

    def publish_grades(self, actor, section_id, confirmed=True, ip=None):
        require_role(actor, ROLE_TRAINING)
        if not confirmed:
            return False
        with self._db() as db:
            courses = CourseRepo(db)
            section = courses.find_section(section_id)
            if section is None:
                raise ServiceError("The course section does not exist.")
            if section["grade_status"] != "LOCKED":
                raise ServiceError("Grades must be locked before they are published.")
            courses.set_grade_status(section_id, "PUBLISHED")  # BR-10: sinh vien chi thay diem PUBLISHED
            AuditRepo(db).add(actor["account_id"], "GRADE_PUBLISH", "course_section", section_id,
                              "LOCKED->PUBLISHED", ip)
        return True

    def unlock_grades(self, actor, section_id, reason, confirmed=True, ip=None):
        require_role(actor, ROLE_TRAINING)
        if not confirmed:
            return False
        if (reason or "").strip() == "":
            raise ServiceError("A reason is required to unlock grades (BR-10).")
        with self._db() as db:
            courses = CourseRepo(db)
            section = courses.find_section(section_id)
            if section is None:
                raise ServiceError("The course section does not exist.")
            if section["grade_status"] == "UNLOCKED":
                raise ServiceError("The grade sheet is already unlocked.")
            courses.set_grade_status(section_id, "UNLOCKED")  # diem da cong bo bi rut khoi tam nhin sinh vien
            AuditRepo(db).add(actor["account_id"], "GRADE_UNLOCK", "course_section", section_id,
                              "%s->UNLOCKED reason=%s" % (section["grade_status"], reason.strip()), ip)
        return True