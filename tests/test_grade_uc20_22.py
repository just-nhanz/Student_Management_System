import pytest

from app.services import PermissionDenied, ServiceError
from app.services.enroll_service import EnrollService
from app.services.grade_service import GradeService, letter_for

SEC_A = "INT101-2026-2-01"


def make_entry(row, process, exam, reason=""):
    return {
        "registration_id": row["registration_id"],
        "process_score": process,
        "exam_score": exam,
        "version": row["version"],
        "reason": reason,
    }


def get_first_row(lecturer):
    return GradeService().grade_sheet(lecturer, SEC_A)["rows"][0]


# UC20 - lich giang day
def test_teaching_schedule(lecturer, make_lecturer):
    svc = GradeService()
    data = svc.teaching_schedule(lecturer)
    assert len(data["sections"]) == 2

    # giang vien moi chua duoc phan cong -> danh sach rong
    other = make_lecturer("GV050")
    assert svc.teaching_schedule(other)["sections"] == []

    # hoc ky khong ton tai
    with pytest.raises(ServiceError):
        svc.teaching_schedule(lecturer, "1999-1")


# UC21 - danh sach lop
def test_class_list_only_successful_and_own_section(lecturer, student, make_lecturer):
    enroll = EnrollService()
    svc = GradeService()

    enroll.register(student, SEC_A)
    info = svc.class_list(lecturer, SEC_A)
    assert info["total"] == 1
    assert info["rows"][0]["student_id"] == "SV001"

    # sv huy dang ky thi khong con trong danh sach
    enroll.drop(student, SEC_A)
    assert svc.class_list(lecturer, SEC_A)["total"] == 0

    # GV khac, khong duoc phan cong lop nay
    with pytest.raises(PermissionDenied):
        svc.class_list(make_lecturer("GV051"), SEC_A)


# UC22 - nhap diem
def test_enter_grades_and_final_score(lecturer, student):
    EnrollService().register(student, SEC_A)
    row = get_first_row(lecturer)

    saved_count = GradeService().save_sheet(lecturer, SEC_A, [make_entry(row, "8", "9")])
    assert saved_count == 1

    saved = get_first_row(lecturer)
    # 40% qua trinh + 60% cuoi ky = 0.4*8 + 0.6*9
    assert float(saved["final_score"]) == pytest.approx(8.6)
    assert saved["letter_grade"] == "A"


def test_score_validation(lecturer, student):
    EnrollService().register(student, SEC_A)
    row = get_first_row(lecturer)

    for invalid in ("11", "-1", "abc"):
        with pytest.raises(ServiceError):
            GradeService().save_sheet(lecturer, SEC_A, [make_entry(row, invalid, "5")])


def test_change_requires_reason_and_logs(lecturer, student, sql):
    EnrollService().register(student, SEC_A)
    svc = GradeService()

    # lan nhap dau khong can ly do
    svc.save_sheet(lecturer, SEC_A, [make_entry(get_first_row(lecturer), "8", "9")])
    row = get_first_row(lecturer)

    # sua diem ma khong ghi ly do -> bi tu choi
    with pytest.raises(ServiceError):
        svc.save_sheet(lecturer, SEC_A, [make_entry(row, "8", "10")])

    svc.save_sheet(lecturer, SEC_A, [make_entry(row, "8", "10", "regrade")])
    assert float(get_first_row(lecturer)["final_score"]) == pytest.approx(9.2)

    # BR-13: moi lan ghi diem deu co log
    logs = sql("SELECT detail FROM audit_log WHERE action = 'GRADE_UPDATE'")
    assert len(logs) == 2
    assert "regrade" in logs[1]["detail"]


def test_version_conflict_rejected(lecturer, student):
    EnrollService().register(student, SEC_A)
    svc = GradeService()

    svc.save_sheet(lecturer, SEC_A, [make_entry(get_first_row(lecturer), "8", "9")])
    stale = get_first_row(lecturer)

    # co nguoi khac sua truoc, version cua `stale` bi cu
    svc.save_sheet(lecturer, SEC_A, [make_entry(stale, "8", "7", "fix")])

    with pytest.raises(ServiceError) as exc:
        svc.save_sheet(lecturer, SEC_A, [make_entry(stale, "8", "6", "again")])
    assert "reload" in exc.value.message.lower()


def test_lock_publish_unlock_flow(lecturer, student, training):
    EnrollService().register(student, SEC_A)
    svc = GradeService()

    # chua nhap diem thi khong khoa duoc, thong bao phai neu ma SV thieu diem
    with pytest.raises(ServiceError) as exc:
        svc.lock_grades(training, SEC_A)
    assert "SV001" in exc.value.message

    svc.save_sheet(lecturer, SEC_A, [make_entry(get_first_row(lecturer), "8", "9")])
    progress = svc.completeness(training, SEC_A)
    assert progress["registered"] == 1
    assert progress["complete"] == 1

    # phai khoa truoc roi moi cong bo
    with pytest.raises(ServiceError):
        svc.publish_grades(training, SEC_A)

    svc.lock_grades(training, SEC_A)
    sheet = svc.grade_sheet(lecturer, SEC_A)
    assert sheet["read_only"] is True

    # bang diem da khoa thi GV khong sua duoc nua
    with pytest.raises(ServiceError):
        svc.save_sheet(lecturer, SEC_A, [make_entry(sheet["rows"][0], "9", "9", "x")])

    svc.publish_grades(training, SEC_A)
    assert len(EnrollService().view_grades(student)["rows"]) == 1

    # mo khoa bat buoc phai co ly do
    with pytest.raises(ServiceError):
        svc.unlock_grades(training, SEC_A, "")

    svc.unlock_grades(training, SEC_A, "correction")
    # sau khi mo khoa, sinh vien khong con thay diem
    assert EnrollService().view_grades(student)["rows"] == []


def test_only_assigned_lecturer_and_academic_manager(make_lecturer, student, lecturer):
    svc = GradeService()

    with pytest.raises(PermissionDenied):
        svc.grade_sheet(make_lecturer("GV052"), SEC_A)

    # giang vien khong co quyen khoa diem
    with pytest.raises(PermissionDenied):
        svc.lock_grades(lecturer, SEC_A)

    # sinh vien khong duoc xem bang diem cua lop
    with pytest.raises(PermissionDenied):
        svc.grade_sheet(student, SEC_A)


def test_letter_scale():
    assert letter_for(9.0) == "A"
    assert letter_for(7.0) == "B"
    assert letter_for(5.5) == "C"
    assert letter_for(4.0) == "D"
    assert letter_for(3.9) == "F"
    assert letter_for(None) is None
