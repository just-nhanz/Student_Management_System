import io

import pytest
from openpyxl import Workbook

from app.services import PermissionDenied, ServiceError
from app.services.catalog_service import CatalogService
from app.services.user_service import UserService
from app.utils.excel_handler import IMPORT_COLUMNS


def student_data(student_id="SV200", **extra):
    data = {"student_id": student_id, "full_name": "Test Student", "date_of_birth": "2005-02-02", "gender": "FEMALE",
            "class_id": "SE2026A", "email": student_id.lower() + "@school.edu.vn", "phone_number": "0912345678"}
    data.update(extra)
    return data


# ------------------------------------------------------------------ UC05
def test_add_student_creates_linked_account(training, sql):
    result = UserService().add_student(training, student_data())
    rows = sql("SELECT a.must_change_password FROM account a WHERE a.username = 'SV200'")
    assert rows[0]["must_change_password"] == 1 and result["temporary_password"] != ""


def test_add_student_duplicate_id_and_email(training):
    service = UserService()
    service.add_student(training, student_data())
    with pytest.raises(ServiceError):
        service.add_student(training, student_data(email="other@school.edu.vn"))
    with pytest.raises(ServiceError):
        service.add_student(training, student_data("SV201", email="sv200@school.edu.vn"))


def test_add_student_validation_errors_per_field(training):
    with pytest.raises(ServiceError) as error:
        UserService().add_student(training, student_data(email="bad-email", phone_number="abc", full_name=""))
    assert "email" in error.value.errors and "phone_number" in error.value.errors and "full_name" in error.value.errors


def test_only_academic_manager_manages_students(student, finance):
    with pytest.raises(PermissionDenied):
        UserService().add_student(student, student_data())
    with pytest.raises(PermissionDenied):
        UserService().search_students(finance)


def test_soft_delete_keeps_record(training, sql):
    assert UserService().delete_student(training, "SV001") is True
    rows = sql("SELECT record_status FROM student WHERE student_id = 'SV001'")
    assert rows[0]["record_status"] == "INACTIVE"   # BR-02: khong xoa vat ly


def test_search_and_empty_result(training):
    service = UserService()
    assert service.search_students(training, "SV001")["total"] == 1
    assert service.search_students(training, "zzzz")["total"] == 0


def make_excel(rows):
    wb = Workbook()
    ws = wb.active
    ws.append(IMPORT_COLUMNS)
    for row in rows:
        ws.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_import_excel_preview_and_confirm(training, sql):
    content = make_excel([
        ["SV300", "Valid One", "2005-01-20", "MALE", "SE2026A", "sv300@school.edu.vn", "0912345678", ""],
        ["SV301", "Bad Email", "2005-01-20", "MALE", "SE2026A", "not-an-email", "", ""],
        ["SV300", "Duplicate In File", "2005-01-20", "MALE", "SE2026A", "dup@school.edu.vn", "", ""],
    ])
    service = UserService()
    preview = service.preview_student_import(training, content)
    assert len(preview["valid_rows"]) == 1 and len(preview["errors"]) == 2
    assert service.student_error_report(preview["errors"])[:2] == b"PK"   # file xlsx
    result = service.confirm_student_import(training, preview["valid_rows"])
    assert result["imported"] == 1
    assert len(sql("SELECT * FROM student WHERE student_id = 'SV300'")) == 1


def test_import_rejects_missing_column_and_bad_file(training):
    wb = Workbook()
    wb.active.append(["student_id", "full_name"])
    buffer = io.BytesIO()
    wb.save(buffer)
    assert UserService().preview_student_import(training, buffer.getvalue())["file_error"]
    assert UserService().preview_student_import(training, b"not an excel file")["file_error"]


# ------------------------------------------------------------------ UC06
def test_lecturer_add_duplicate_and_delete_rules(training):
    service = UserService()
    data = {"lecturer_id": "GV010", "full_name": "New Lecturer", "faculty_id": "IT", "email": "gv010@school.edu.vn"}
    service.add_lecturer(training, data)
    with pytest.raises(ServiceError):
        service.add_lecturer(training, data)
    with pytest.raises(ServiceError):                 # GV001 dang duoc phan cong -> khong cho vo hieu hoa
        service.delete_lecturer(training, "GV001")
    assert service.delete_lecturer(training, "GV010") is True


def test_lecturer_search(training):
    assert UserService().search_lecturers(training, "GV001")["total"] == 1
    assert UserService().search_lecturers(training, "nobody")["total"] == 0
