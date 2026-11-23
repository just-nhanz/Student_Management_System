import pytest

from app.services import PermissionDenied, ServiceError
from app.services.enroll_service import EnrollService
from app.services.grade_service import GradeService

SEC_A = "INT101-2026-2-01"   # ngay 2, tiet 1-3, phong A101
SEC_B = "INT301-2026-2-01"   # ngay 4, tiet 1-3, phong A102


# ------------------------------------------------------------------ UC08
def test_open_section_default_status(training, sql):
    section_id = EnrollService().open_section(training, "INT201", "2026-2", "B1", 6, 1, 3, 30)
    assert section_id == "INT201-2026-2-01"
    row = sql("SELECT status, grade_status FROM course_section WHERE course_section_id = %s", (section_id,))[0]
    assert row["status"] == "OPEN" and row["grade_status"] == "UNLOCKED"


def test_open_section_validations(training):
    service = EnrollService()
    with pytest.raises(ServiceError):
        service.open_section(training, "INT201", "2026-2", "A101", 2, 2, 2, 30)     # trung phong
    with pytest.raises(ServiceError):
        service.open_section(training, "INT201", "2026-2", "B1", 6, 1, 3, 0)        # suc chua > 0
    with pytest.raises(ServiceError):
        service.open_section(training, "NOPE", "2026-2", "B1", 6, 1, 3, 30)         # mon khong ton tai


def test_discontinued_subject_cannot_be_opened(training):
    from app.services.catalog_service import CatalogService
    CatalogService().discontinue_subject(training, "INT201")
    with pytest.raises(ServiceError):
        EnrollService().open_section(training, "INT201", "2026-2", "B1", 6, 1, 3, 30)


def test_only_academic_manager_opens_sections(student):
    with pytest.raises(PermissionDenied):
        EnrollService().open_section(student, "INT201", "2026-2", "B1", 6, 1, 3, 30)


# ------------------------------------------------------------------ UC09
def test_assign_lecturer_and_conflict(training, open_section):
    service = EnrollService()
    free = open_section("INT201", "B1", 6, 1, 3, 30)
    assert service.assign_lecturer(training, free, "GV001") is True
    clash = open_section("INT301", "B2", 2, 2, 2, 30)     # cung ngay 2, tiet 2-3 voi SEC_A cua GV001
    with pytest.raises(ServiceError):
        service.assign_lecturer(training, clash, "GV001")
    with pytest.raises(ServiceError):
        service.assign_lecturer(training, free, "GV999")  # giang vien khong ton tai


# ------------------------------------------------------------------ UC10
def test_register_success_and_debt_calculated(student):
    assert EnrollService().register(student, SEC_A) is True
    from app.services.fee_service import FeeService
    debts = FeeService().student_status(student)["debts"]
    assert float(debts[0]["total_payable"]) == 1500000.0       # BR-11: 3 tin chi x 500000


def test_register_duplicate_rejected(student):
    EnrollService().register(student, SEC_A)
    with pytest.raises(ServiceError):
        EnrollService().register(student, SEC_A)


def test_register_prerequisite_missing(student, open_section):
    section = open_section("INT201", "B1", 6, 1, 3, 30)        # INT201 yeu cau INT101
    with pytest.raises(ServiceError) as error:
        EnrollService().register(student, section)
    assert "INT101" in error.value.message


def test_register_schedule_conflict(student, open_section):
    EnrollService().register(student, SEC_A)
    clash = open_section("INT301", "B2", 2, 2, 2, 30)
    with pytest.raises(ServiceError) as error:
        EnrollService().register(student, clash)
    assert SEC_A in error.value.message


def test_register_full_section(student, make_student, open_section):
    section = open_section("INT301", "B3", 5, 1, 3, 1)         # chi 1 cho
    other = make_student("SV900")
    EnrollService().register(other, section)
    with pytest.raises(ServiceError) as error:
        EnrollService().register(student, section)
    assert "full" in error.value.message.lower()


def test_register_credit_limit(student, sql):
    sql("UPDATE semester SET max_credits = 3 WHERE semester_id = '2026-2'")
    EnrollService().register(student, SEC_A)
    with pytest.raises(ServiceError) as error:
        EnrollService().register(student, SEC_B)
    assert "credit limit" in error.value.message.lower()


def test_register_blocked_by_overdue_debt(student, sql):
    EnrollService().register(student, SEC_A)
    sql("UPDATE student_debt SET due_date = DATE_SUB(CURDATE(), INTERVAL 3 DAY)")
    with pytest.raises(ServiceError) as error:
        EnrollService().register(student, SEC_B)
    assert "debt" in error.value.message.lower()


def test_register_outside_period(student, sql):
    sql("UPDATE semester SET reg_end = DATE_SUB(NOW(), INTERVAL 1 HOUR)")
    with pytest.raises(ServiceError) as error:
        EnrollService().register(student, SEC_A)
    assert "closed" in error.value.message.lower()


def test_register_closed_section(student, sql):
    sql("UPDATE course_section SET status = 'CLOSED' WHERE course_section_id = %s", (SEC_A,))
    with pytest.raises(ServiceError):
        EnrollService().register(student, SEC_A)


def test_lecturer_cannot_register(lecturer):
    with pytest.raises(PermissionDenied):
        EnrollService().register(lecturer, SEC_A)


# ------------------------------------------------------------------ UC11
def test_drop_requires_confirmation_then_cancels(student):
    service = EnrollService()
    service.register(student, SEC_A)
    assert service.drop(student, SEC_A, confirmed=False) is False
    assert len(service.view_schedule(student)["rows"]) == 1
    assert service.drop(student, SEC_A, confirmed=True) is True
    assert len(service.view_schedule(student)["rows"]) == 0


def test_drop_after_deadline_rejected(student, sql):
    EnrollService().register(student, SEC_A)
    sql("UPDATE semester SET cancel_deadline = reg_start")
    with pytest.raises(ServiceError):
        EnrollService().drop(student, SEC_A)


def test_drop_unregistered_rejected(student):
    with pytest.raises(ServiceError):
        EnrollService().drop(student, SEC_A)


def test_reregister_after_cancel_reuses_row(student, sql):
    service = EnrollService()
    service.register(student, SEC_A)
    service.drop(student, SEC_A)
    service.register(student, SEC_A)
    assert len(sql("SELECT * FROM course_registration WHERE student_id = 'SV001'")) == 1


# ------------------------------------------------------------------ UC12
def test_view_schedule_and_invalid_semester(student):
    service = EnrollService()
    assert len(service.view_schedule(student)["rows"]) == 0
    service.register(student, SEC_A)
    rows = service.view_schedule(student)["rows"]
    assert rows[0]["subject_name"] == "Programming Fundamentals" and rows[0]["classroom"] == "A101"
    with pytest.raises(ServiceError):
        service.view_schedule(student, "1999-1")


# ------------------------------------------------------------------ UC13
def test_grades_visible_only_when_published(student, training, lecturer):
    EnrollService().register(student, SEC_A)
    grades = GradeService()
    sheet = grades.grade_sheet(lecturer, SEC_A)
    row = sheet["rows"][0]
    grades.save_sheet(lecturer, SEC_A, [{"registration_id": row["registration_id"], "process_score": "7",
                                         "exam_score": "8", "version": row["version"], "reason": ""}])
    assert EnrollService().view_grades(student)["rows"] == []        # chua cong bo
    grades.lock_grades(training, SEC_A)
    assert EnrollService().view_grades(student)["rows"] == []        # moi khoa, chua cong bo
    grades.publish_grades(training, SEC_A)
    result = EnrollService().view_grades(student)["rows"]
    assert len(result) == 1 and result[0]["result"] == "PASSED"
