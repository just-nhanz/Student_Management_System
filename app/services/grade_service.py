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
    if final_score is None:
        return None
    for minimum, letter in Config.LETTER_SCALE:
        if final_score >= minimum:
            return letter
    return "F"


def parse_score(text):
    if text is None or str(text).strip() == "":
        return None, None
    try:
        value = float(str(text).strip())
    except ValueError:
        return None, "Score must be a number."
    if value < 0 or value > 10:
        return None, "Score must be between 0 and 10."
    return round(value, 2), None


def _as_float(grade, field):
    if grade is None or grade[field] is None:
        return None
    return float(grade[field])


class GradeService:

    def __init__(self, connection=None):
        self.connection = connection

    def _db(self):
        return Database(self.connection)

    def _own_section(self, db, user, section_id):
        lecturer = UserRepo(db).find_lecturer_by_account(user["account_id"])
        section = CourseRepo(db).find_section(section_id)
        if lecturer is None or section is None or section["lecturer_id"] != lecturer["lecturer_id"]:
            raise PermissionDenied("This course section is not assigned to you.")
        return lecturer, section

    def _section_or_fail(self, courses, section_id):
        section = courses.find_section(section_id)
        if section is None:
            raise ServiceError("The course section does not exist.")
        return section

    # UC20: lich giang day
    def teaching_schedule(self, user, semester_id=None):
        require_role(user, ROLE_LECTURER)
        with self._db() as db:
            catalog = CatalogRepo(db)
            lecturer = UserRepo(db).find_lecturer_by_account(user["account_id"])
            if semester_id and catalog.find_semester(semester_id) is None:
                raise ServiceError("Invalid semester. Please choose again.")
            semester_id = semester_id or current_semester_id(catalog)
            sections = []
            if semester_id:
                sections = list(CourseRepo(db).list_by_lecturer(lecturer["lecturer_id"], semester_id))
            return {
                "semester_id": semester_id,
                "sections": sections,
                "semesters": list(catalog.list_semesters()),
            }

    def class_list(self, user, section_id, page=1):
        require_role(user, ROLE_LECTURER)
        with self._db() as db:
            lecturer, section = self._own_section(db, user, section_id)
            enroll = EnrollRepo(db)
            info = page_info(enroll.count_successful(section_id), page)
            info["rows"] = enroll.list_class(section_id, info["offset"], info["limit"])
            info["section"] = section
            return info

    def grade_sheet(self, user, section_id):
        require_role(user, ROLE_LECTURER)
        with self._db() as db:
            lecturer, section = self._own_section(db, user, section_id)
            rows = GradeRepo(db).list_sheet(section_id)
            return {
                "section": section,
                "rows": rows,
                "read_only": section["grade_status"] != "UNLOCKED",
            }

    def _collect_changes(self, db, section_id, entries):
        grades = GradeRepo(db)
        enroll = EnrollRepo(db)
        changes = []
        errors = {}

        for entry in entries:
            reg_id = int(entry["registration_id"])
            reg = enroll.find_registration_by_id(reg_id)
            if reg is None or reg["course_section_id"] != section_id or reg["status"] != "SUCCESSFUL":
                raise ServiceError("Registration %s does not belong to this section." % reg_id)

            label = "row %s" % reg["student_id"]
            process, err_process = parse_score(entry.get("process_score"))
            exam, err_exam = parse_score(entry.get("exam_score"))
            if err_process or err_exam:
                errors[label] = err_process or err_exam
                continue

            old = grades.find_grade(reg_id)
            old_process = _as_float(old, "process_score")
            old_exam = _as_float(old, "exam_score")
            if old is not None and old_process == process and old_exam == exam:
                continue
            reason = (entry.get("reason") or "").strip()
            had_score = old_process is not None or old_exam is not None
            if had_score and reason == "":
                errors[label] = "A reason is required to change an existing score."
                continue

            changes.append({
                "reg_id": reg_id,
                "student_id": reg["student_id"],
                "old": old,
                "old_scores": (old_process, old_exam),
                "new_scores": (process, exam),
                "reason": reason,
                "version": entry.get("version"),
            })
        return changes, errors

    def _apply_change(self, db, grades, user, change, ip):
        reg_id = change["reg_id"]
        old = change["old"]
        process, exam = change["new_scores"]

        if old is None:
            grades.insert_grade(reg_id, process, exam, user["account_id"])
        else:
            version = change["version"]
            if version is None or int(version) != old["version"]:
                stale = True
            else:
                stale = grades.update_grade(old["grade_id"], process, exam, old["version"],
                                            user["account_id"]) == 0
            if stale:
                raise ServiceError("Another user changed the grade of student %s. Please reload the sheet."
                                   % change["student_id"])

        fresh = grades.find_grade(reg_id)
        grades.set_letter_grade(fresh["grade_id"], letter_for(fresh["final_score"]))

        old_process, old_exam = change["old_scores"]
        detail = "old=(%s,%s) new=(%s,%s) reason=%s" % (old_process, old_exam, process, exam, change["reason"])
        AuditRepo(db).add(user["account_id"], "GRADE_UPDATE", "grade", str(reg_id), detail, ip)  # BR-13

    def save_sheet(self, user, section_id, entries, ip=None):
        require_role(user, ROLE_LECTURER)
        with self._db() as db:
            lecturer, section = self._own_section(db, user, section_id)
            if section["grade_status"] != "UNLOCKED":
                raise ServiceError("The grade sheet is read-only. The Academic Manager must unlock it first (UC08).")

            changes, errors = self._collect_changes(db, section_id, entries)
            if errors:
                raise validation_error(errors)

            grades = GradeRepo(db)
            for change in changes:
                self._apply_change(db, grades, user, change, ip)
            return len(changes)

    def completeness(self, actor, section_id):
        require_role(actor, ROLE_TRAINING)
        with self._db() as db:
            section = self._section_or_fail(CourseRepo(db), section_id)
            registered, complete = GradeRepo(db).count_registered_and_complete(section_id)
            return {"section": section, "registered": registered, "complete": complete}

    def lock_grades(self, actor, section_id, confirmed=True, ip=None):
        require_role(actor, ROLE_TRAINING)
        if not confirmed:
            return False
        with self._db() as db:
            courses = CourseRepo(db)
            section = self._section_or_fail(courses, section_id)
            if section["grade_status"] != "UNLOCKED":
                raise ServiceError("Only an Unlocked grade sheet can be locked.")

            missing = GradeRepo(db).list_incomplete(section_id)
            if missing:
                who = ", ".join("%s (%s)" % (r["student_id"], r["full_name"]) for r in missing)
                raise ServiceError("Cannot lock: these students have no final score - " + who)

            courses.set_grade_status(section_id, "LOCKED")
            AuditRepo(db).add(actor["account_id"], "GRADE_LOCK", "course_section", section_id,
                              "UNLOCKED->LOCKED", ip)
        return True

    def publish_grades(self, actor, section_id, confirmed=True, ip=None):
        require_role(actor, ROLE_TRAINING)
        if not confirmed:
            return False
        with self._db() as db:
            courses = CourseRepo(db)
            section = self._section_or_fail(courses, section_id)
            if section["grade_status"] != "LOCKED":
                raise ServiceError("Grades must be locked before they are published.")

            courses.set_grade_status(section_id, "PUBLISHED")
            AuditRepo(db).add(actor["account_id"], "GRADE_PUBLISH", "course_section", section_id,
                              "LOCKED->PUBLISHED", ip)
        return True

    def unlock_grades(self, actor, section_id, reason, confirmed=True, ip=None):
        require_role(actor, ROLE_TRAINING)
        if not confirmed:
            return False
        reason = (reason or "").strip()
        if reason == "":
            raise ServiceError("A reason is required to unlock grades (BR-10).")
        with self._db() as db:
            courses = CourseRepo(db)
            section = self._section_or_fail(courses, section_id)
            if section["grade_status"] == "UNLOCKED":
                raise ServiceError("The grade sheet is already unlocked.")

            courses.set_grade_status(section_id, "UNLOCKED")
            AuditRepo(db).add(actor["account_id"], "GRADE_UNLOCK", "course_section", section_id,
                              "%s->UNLOCKED reason=%s" % (section["grade_status"], reason), ip)
        return True
