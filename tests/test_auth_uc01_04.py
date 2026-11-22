"""UC01-UC04. TC01, TC02, TC03 cua file Testing_Document_Template.xlsx.
TC03 (Register Account): SRS khong co man hinh tu dang ky; tai khoan duoc tao cung ho so (UC05) hoac boi
System Administrator (UC04), nen kich ban TC03 duoc kiem thu qua UC05 voi du lieu Name/Email/Username/Password cua TC03.
"""
import pytest

from app.services import PermissionDenied, ServiceError
from app.services.auth_service import AuthService
from app.services.user_service import UserService


def test_tc01_login_success():
    user = AuthService().login("student01", "123456")
    assert user["username"] == "student01"
    assert user["roles"] == ["STUDENT"]


def test_tc02_login_wrong_password_shows_generic_message():
    with pytest.raises(ServiceError) as error:
        AuthService().login("student01", "wrongpass")
    assert error.value.message == "Invalid username or password."


def test_login_unknown_user_same_generic_message(sql):
    with pytest.raises(ServiceError) as error:
        AuthService().login("nobody", "123456")
    assert error.value.message == "Invalid username or password."
    logs = sql("SELECT * FROM audit_log WHERE action = 'LOGIN_FAILED'")   # BR-13
    assert len(logs) == 1


def test_login_empty_fields():
    with pytest.raises(ServiceError):
        AuthService().login("", "")


def test_account_locked_after_5_failures(sql):
    for _ in range(5):
        with pytest.raises(ServiceError):
            AuthService().login("student01", "bad")
    rows = sql("SELECT status FROM account WHERE username = 'student01'")
    assert rows[0]["status"] == "LOCKED"
    with pytest.raises(ServiceError):
        AuthService().login("student01", "123456")   # tai khoan khoa: tu choi ca khi dung mat khau


def test_tc03_register_account_via_profile_creation(training, sql):
    # Dua tai khoan mau ra khoi he thong de TC03 dung lai username student01
    sql("DELETE FROM account_role WHERE account_id = 5")
    sql("DELETE FROM student WHERE account_id = 5")
    sql("DELETE FROM account WHERE account_id = 5")
    data = {"student_id": "student01", "full_name": "John", "email": "john@gmail.com",
            "date_of_birth": "2005-05-05", "gender": "MALE", "class_id": "SE2026A"}
    UserService().add_student(training, data, initial_password="123456")
    user = AuthService().login("student01", "123456")
    assert user["full_name"] == "John"
    assert user["must_change_password"] is True


def test_register_duplicate_username_rejected(training):
    data = {"student_id": "student01", "full_name": "John", "email": "john@gmail.com",
            "date_of_birth": "2005-05-05", "gender": "MALE", "class_id": "SE2026A"}
    with pytest.raises(ServiceError):   # BR-01: username duy nhat
        UserService().add_student(training, data)


def test_logout_requires_confirmation(student):
    assert AuthService().logout(student, confirmed=False) is False
    assert AuthService().logout(student, confirmed=True) is True


def test_change_password_rules(student):
    service = AuthService()
    with pytest.raises(ServiceError):
        service.change_password(student, "wrong", "newpass1", "newpass1")
    with pytest.raises(ServiceError):
        service.change_password(student, "123456", "newpass1", "different")
    with pytest.raises(ServiceError):
        service.change_password(student, "123456", "123", "123")          # vi pham chinh sach
    with pytest.raises(ServiceError):
        service.change_password(student, "123456", "123456", "123456")    # trung mat khau cu
    assert service.change_password(student, "123456", "newpass1", "newpass1") is True
    assert service.login("student01", "newpass1")["username"] == "student01"


def test_admin_creates_account_and_temp_password_must_change(admin):
    service = AuthService()
    result = service.create_account(admin, "manager2", "Manager Two", "m2@school.edu.vn", "", ["FINANCE_MANAGER"])
    user = service.login("manager2", result["temporary_password"])
    assert user["must_change_password"] is True
    assert user["roles"] == ["FINANCE_MANAGER"]
    with pytest.raises(ServiceError):   # username trung
        service.create_account(admin, "manager2", "X", "x@school.edu.vn", "", ["FINANCE_MANAGER"])
    with pytest.raises(ServiceError):   # thieu vai tro
        service.create_account(admin, "m3", "X", "m3@school.edu.vn", "", [])


def test_only_admin_manages_accounts(student, training):
    with pytest.raises(PermissionDenied):
        AuthService().list_accounts(student)
    with pytest.raises(PermissionDenied):
        AuthService().create_account(training, "u", "U", "u@x.vn", "", ["FINANCE_MANAGER"])


def test_lock_unlock_rules(admin):
    service = AuthService()
    with pytest.raises(ServiceError):
        service.lock_account(admin, admin["account_id"], "test")        # khong tu khoa
    with pytest.raises(ServiceError):
        service.lock_account(admin, 5, "")                              # bat buoc co ly do
    assert service.lock_account(admin, 5, "policy") is True
    with pytest.raises(ServiceError):
        service.login("student01", "123456")
    assert service.unlock_account(admin, 5) is True
    assert service.login("student01", "123456") is not None


def test_reset_password_sets_must_change(admin):
    new_password = AuthService().reset_password(admin, 5)
    user = AuthService().login("student01", new_password)
    assert user["must_change_password"] is True


def test_cannot_remove_last_admin_role(admin):
    with pytest.raises(ServiceError):
        AuthService().assign_roles(admin, admin["account_id"], ["FINANCE_MANAGER"])
    assert AuthService().assign_roles(admin, 5, ["STUDENT", "LECTURER"]) is True
