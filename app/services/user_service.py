from datetime import date

from app.config import ROLE_ADMIN, ROLE_LECTURER, ROLE_STUDENT, ROLE_TRAINING
from app.repositories.account_repo import AccountRepo
from app.repositories.audit_repo import AuditRepo
from app.repositories.catalog_repo import CatalogRepo
from app.repositories.user_repo import UserRepo
from app.services import (ServiceError, generate_temp_password, page_info, parse_date, require_role,
                          validation_error)
from app.utils.database import Database
from app.utils.excel_handler import read_student_rows, build_error_report
from app.utils.security import (check_password_policy, hash_password, is_valid_email, is_valid_phone)

GENDERS = ["MALE", "FEMALE", "OTHER"]
ACADEMIC_STATUSES = ["STUDYING", "ON_LEAVE", "DROPPED_OUT", "GRADUATED"]


class UserService:
    """UC05, UC06: ho so sinh vien va giang vien."""

    def __init__(self, connection=None):
        self.connection = connection

    def _db(self):
        return Database(self.connection)

    # ------------------------------------------------------------- kiem tra du lieu
    def _check_student_fields(self, data, catalog):
        """UC05.2.2: kiem tra truong bat buoc, dinh dang email/dien thoai; tra ve dict loi theo truong."""
        errors = {}
        student_id = (data.get("student_id") or "").strip()
        if student_id == "" or len(student_id) > 12:
            errors["student_id"] = "Required (max 12 characters)."
        if (data.get("full_name") or "").strip() == "" or len(data.get("full_name") or "") > 100:
            errors["full_name"] = "Required (max 100 characters)."
        try:
            dob = parse_date(data.get("date_of_birth"), "date_of_birth")
            if dob >= date.today():
                errors["date_of_birth"] = "Must be in the past."
        except ServiceError:
            errors["date_of_birth"] = "Invalid date (use YYYY-MM-DD)."
        if data.get("gender") not in GENDERS:
            errors["gender"] = "Must be MALE, FEMALE or OTHER."
        class_row = catalog.find_class(data.get("class_id") or "")
        if class_row is None or class_row["status"] != "ACTIVE":
            errors["class_id"] = "Administrative class does not exist."
        if not is_valid_email(data.get("email")):
            errors["email"] = "Invalid e-mail format."
        if not is_valid_phone(data.get("phone_number")):
            errors["phone_number"] = "Invalid phone number."
        return errors

    # ------------------------------------------------------------- UC05
    def add_student(self, actor, data, initial_password=None, ip=None):
        """UC05: them ho so va tao tai khoan (username = ma sinh vien, mat khau tam, buoc doi mat khau)."""
        require_role(actor, ROLE_TRAINING)
        with self._db() as db:
            catalog = CatalogRepo(db)
            users = UserRepo(db)
            accounts = AccountRepo(db)
            errors = self._check_student_fields(data, catalog)
            if errors:
                raise validation_error(errors)
            student_id = data["student_id"].strip()
            if initial_password:
                policy_error = check_password_policy(initial_password)
                if policy_error:
                    raise validation_error({"password": policy_error})
            # UC05.2.2 / BR-01: ma sinh vien va email phai duy nhat
            if users.find_student(student_id) is not None or accounts.find_by_username(student_id) is not None:
                raise ServiceError("Student ID already exists.", {"student_id": "Already exists."})
            if accounts.find_by_email(data["email"]) is not None:
                raise ServiceError("E-mail already exists.", {"email": "Already exists."})
            temp_password = initial_password or generate_temp_password()
            account_id = accounts.insert(student_id, hash_password(temp_password), data["full_name"].strip(),
                                         data["email"], data.get("phone_number") or None, 1)
            accounts.add_role(account_id, accounts.get_role_id(ROLE_STUDENT))
            users.insert_student(student_id, account_id, data["class_id"], parse_date(data["date_of_birth"], "dob"),
                                 data["gender"], data.get("address") or None)
            AuditRepo(db).add(actor["account_id"], "PROFILE_ADD", "student", student_id, None, ip)
        return {"student_id": student_id, "temporary_password": temp_password}

    def update_student(self, actor, student_id, data, ip=None):
        require_role(actor, ROLE_TRAINING)
        with self._db() as db:
            catalog = CatalogRepo(db)
            users = UserRepo(db)
            accounts = AccountRepo(db)
            current = users.find_student(student_id)
            if current is None:
                raise ServiceError("Student not found.")
            data = dict(data)
            data["student_id"] = student_id
            errors = self._check_student_fields(data, catalog)
            academic_status = data.get("academic_status") or current["academic_status"]
            if academic_status not in ACADEMIC_STATUSES:
                errors["academic_status"] = "Invalid status."
            if errors:
                raise validation_error(errors)
            other = accounts.find_by_email(data["email"])
            if other is not None and other["account_id"] != current["account_id"]:
                raise ServiceError("E-mail already exists.", {"email": "Already exists."})
            accounts.update_contact(current["account_id"], data["full_name"].strip(), data["email"],
                                    data.get("phone_number") or None)
            users.update_student(student_id, data["class_id"], parse_date(data["date_of_birth"], "dob"),
                                 data["gender"], data.get("address") or None, academic_status)
            AuditRepo(db).add(actor["account_id"], "PROFILE_UPDATE", "student", student_id, None, ip)
        return True

    def delete_student(self, actor, student_id, confirmed=True, ip=None):
        """UC05 / BR-02: 'xoa' luon la vo hieu hoa (soft delete), khong xoa vat ly."""
        require_role(actor, ROLE_TRAINING)
        if not confirmed:
            return False
        with self._db() as db:
            users = UserRepo(db)
            if users.find_student(student_id) is None:
                raise ServiceError("Student not found.")
            users.set_student_record_status(student_id, "INACTIVE")
            AuditRepo(db).add(actor["account_id"], "PROFILE_DELETE", "student", student_id, "soft delete", ip)
        return True

    def get_student(self, actor, student_id):
        require_role(actor, ROLE_TRAINING)
        with self._db() as db:
            row = UserRepo(db).find_student(student_id)
            if row is None:
                raise ServiceError("Student not found.")
            return row

    def search_students(self, actor, keyword="", class_id="", page=1):
        require_role(actor, ROLE_TRAINING)
        with self._db() as db:
            users = UserRepo(db)
            total = users.count_students(keyword, class_id)
            info = page_info(total, page)
            info["rows"] = users.search_students(keyword, class_id, info["offset"], info["limit"])
            return info

    # ---- import Excel (UC05) ----
    def preview_student_import(self, actor, file_bytes):
        """Kiem tra file + tung dong; chua ghi gi vao CSDL. Tra ve valid_rows, errors, file_error."""
        require_role(actor, ROLE_TRAINING)
        rows, file_error = read_student_rows(file_bytes)
        if file_error:
            return {"file_error": file_error, "valid_rows": [], "errors": []}
        valid_rows = []
        errors = []
        seen_ids = []
        seen_emails = []
        with self._db() as db:
            catalog = CatalogRepo(db)
            users = UserRepo(db)
            accounts = AccountRepo(db)
            for row in rows:
                row_errors = self._check_student_fields(row, catalog)
                student_id = (row.get("student_id") or "").strip()
                if student_id != "" and (student_id in seen_ids or users.find_student(student_id) is not None
                                         or accounts.find_by_username(student_id) is not None):
                    row_errors["student_id"] = "Duplicate student ID."
                email = row.get("email") or ""
                if email != "" and (email in seen_emails or accounts.find_by_email(email) is not None):
                    row_errors["email"] = "Duplicate e-mail."
                seen_ids.append(student_id)
                seen_emails.append(email)
                if row_errors:
                    messages = []
                    for name, msg in row_errors.items():
                        messages.append("%s: %s" % (name, msg))
                    errors.append((row["row_no"], student_id, "; ".join(messages)))
                else:
                    valid_rows.append(row)
        return {"file_error": None, "valid_rows": valid_rows, "errors": errors}

    def confirm_student_import(self, actor, valid_rows, ip=None):
        """Nhap cac dong hop le trong MOT transaction; tai khoan dung chung mot mat khau tam cua lo nhap."""
        require_role(actor, ROLE_TRAINING)
        temp_password = generate_temp_password()
        password_hash = hash_password(temp_password)
        imported = 0
        with self._db() as db:
            users = UserRepo(db)
            accounts = AccountRepo(db)
            student_role = accounts.get_role_id(ROLE_STUDENT)
            for row in valid_rows:
                account_id = accounts.insert(row["student_id"], password_hash, row["full_name"], row["email"],
                                             row.get("phone_number") or None, 1)
                accounts.add_role(account_id, student_role)
                users.insert_student(row["student_id"], account_id, row["class_id"],
                                     parse_date(row["date_of_birth"], "dob"), row["gender"],
                                     row.get("address") or None)
                imported += 1
            AuditRepo(db).add(actor["account_id"], "PROFILE_IMPORT", "student", None, "rows=%d" % imported, ip)
        return {"imported": imported, "temporary_password": temp_password}

    def student_error_report(self, errors):
        return build_error_report(errors)

    # ------------------------------------------------------------- UC06
    def add_lecturer(self, actor, data, initial_password=None, ip=None):
        require_role(actor, ROLE_TRAINING)
        errors = {}
        lecturer_id = (data.get("lecturer_id") or "").strip()
        if lecturer_id == "" or len(lecturer_id) > 10:
            errors["lecturer_id"] = "Required (max 10 characters)."
        if (data.get("full_name") or "").strip() == "":
            errors["full_name"] = "Required."
        if not is_valid_email(data.get("email")):
            errors["email"] = "Invalid e-mail format."
        if not is_valid_phone(data.get("phone_number")):
            errors["phone_number"] = "Invalid phone number."
        with self._db() as db:
            catalog = CatalogRepo(db)
            users = UserRepo(db)
            accounts = AccountRepo(db)
            faculty = catalog.find_faculty(data.get("faculty_id") or "")
            if faculty is None or faculty["status"] != "ACTIVE":
                errors["faculty_id"] = "Faculty does not exist."
            if errors:
                raise validation_error(errors)
            if users.find_lecturer(lecturer_id) is not None or accounts.find_by_username(lecturer_id) is not None:
                raise ServiceError("Lecturer ID already exists.", {"lecturer_id": "Already exists."})
            if accounts.find_by_email(data["email"]) is not None:
                raise ServiceError("E-mail already exists.", {"email": "Already exists."})
            temp_password = initial_password or generate_temp_password()
            account_id = accounts.insert(lecturer_id, hash_password(temp_password), data["full_name"].strip(),
                                         data["email"], data.get("phone_number") or None, 1)
            accounts.add_role(account_id, accounts.get_role_id(ROLE_LECTURER))
            users.insert_lecturer(lecturer_id, account_id, data["faculty_id"], data.get("degree") or None,
                                  data.get("specialization") or None)
            AuditRepo(db).add(actor["account_id"], "PROFILE_ADD", "lecturer", lecturer_id, None, ip)
        return {"lecturer_id": lecturer_id, "temporary_password": temp_password}

    def update_lecturer(self, actor, lecturer_id, data, ip=None):
        require_role(actor, ROLE_TRAINING)
        errors = {}
        if (data.get("full_name") or "").strip() == "":
            errors["full_name"] = "Required."
        if not is_valid_email(data.get("email")):
            errors["email"] = "Invalid e-mail format."
        if not is_valid_phone(data.get("phone_number")):
            errors["phone_number"] = "Invalid phone number."
        with self._db() as db:
            users = UserRepo(db)
            accounts = AccountRepo(db)
            current = users.find_lecturer(lecturer_id)
            if current is None:
                raise ServiceError("Lecturer not found.")
            if CatalogRepo(db).find_faculty(data.get("faculty_id") or "") is None:
                errors["faculty_id"] = "Faculty does not exist."
            if errors:
                raise validation_error(errors)
            other = accounts.find_by_email(data["email"])
            if other is not None and other["account_id"] != current["account_id"]:
                raise ServiceError("E-mail already exists.", {"email": "Already exists."})
            accounts.update_contact(current["account_id"], data["full_name"].strip(), data["email"],
                                    data.get("phone_number") or None)
            users.update_lecturer(lecturer_id, data["faculty_id"], data.get("degree") or None,
                                  data.get("specialization") or None)
            AuditRepo(db).add(actor["account_id"], "PROFILE_UPDATE", "lecturer", lecturer_id, None, ip)
        return True

    def delete_lecturer(self, actor, lecturer_id, confirmed=True, ip=None):
        """UC06: giang vien dang duoc phan cong phai go phan cong (UC09) truoc khi vo hieu hoa."""
        require_role(actor, ROLE_TRAINING)
        if not confirmed:
            return False
        with self._db() as db:
            users = UserRepo(db)
            if users.find_lecturer(lecturer_id) is None:
                raise ServiceError("Lecturer not found.")
            if users.lecturer_has_sections(lecturer_id):
                raise ServiceError("The lecturer is assigned to course sections. Remove the assignment first (UC09).")
            users.set_lecturer_status(lecturer_id, "INACTIVE")
            AuditRepo(db).add(actor["account_id"], "PROFILE_DELETE", "lecturer", lecturer_id, "soft delete", ip)
        return True

    def search_lecturers(self, actor, keyword="", page=1):
        require_role(actor, ROLE_TRAINING)
        with self._db() as db:
            users = UserRepo(db)
            info = page_info(users.count_lecturers(keyword), page)
            info["rows"] = users.search_lecturers(keyword, info["offset"], info["limit"])
            return info

    def get_lecturer(self, actor, lecturer_id):
        require_role(actor, ROLE_TRAINING)
        with self._db() as db:
            row = UserRepo(db).find_lecturer(lecturer_id)
            if row is None:
                raise ServiceError("Lecturer not found.")
            return row