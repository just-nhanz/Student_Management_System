import time

from app.config import Config, ROLE_ADMIN, ROLE_FINANCE, ROLE_TRAINING
from app.repositories.account_repo import AccountRepo
from app.repositories.audit_repo import AuditRepo
from app.services import (ServiceError, generate_temp_password, require_role, validation_error)
from app.utils.database import Database
from app.utils.security import check_password_policy, hash_password, is_valid_email, is_valid_phone, verify_password

GENERIC_LOGIN_ERROR = "Invalid username or password."   # TC02
STAFF_ROLES = [ROLE_ADMIN, ROLE_TRAINING, ROLE_FINANCE]


class AuthService:
    """UC01 - UC04: dang nhap, dang xuat, doi mat khau, quan ly tai khoan."""

    _ip_hits = {}

    def __init__(self, connection=None):
        self.connection = connection

    def _db(self):
        return Database(self.connection)

    # ------------------------------------------------------------------ UC01
    def login(self, username, password, ip=None):
        username = (username or "").strip()
        # UC01.2.2: de trong truong
        if username == "" or not password:
            raise ServiceError("Please enter both username and password.")
        self._check_rate_limit(ip)  # NFR-SE-06 - toi da 10 yeu cau/phut/IP

        error = None
        user = None
        with self._db() as db:
            accounts = AccountRepo(db)
            audit = AuditRepo(db)
            acc = accounts.find_by_username(username)
            if acc is None:
                # BR-13: ghi log dang nhap that bai (tai khoan khong ton tai -> account_id NULL)
                audit.add(None, "LOGIN_FAILED", "account", username, "Unknown username", ip)
                error = GENERIC_LOGIN_ERROR
            elif acc["status"] == "LOCKED":
                # UC01.2.2: tai khoan bi khoa
                audit.add(acc["account_id"], "LOGIN_FAILED", "account", str(acc["account_id"]), "Account locked", ip)
                error = "This account is locked. Please contact the System Administrator."
            elif not verify_password(password, acc["password_hash"]):
                failed = acc["failed_attempts"] + 1
                accounts.set_failed_attempts(acc["account_id"], failed)
                audit.add(acc["account_id"], "LOGIN_FAILED", "account", str(acc["account_id"]),
                          "Wrong password (attempt %d)" % failed, ip)
                error = GENERIC_LOGIN_ERROR  # khong tiet lo truong nao sai
                if failed >= Config.MAX_FAILED_ATTEMPTS:
                    # UC01 / NFR-SE-06: khoa tai khoan sau 5 lan sai lien tiep
                    accounts.set_status(acc["account_id"], "LOCKED")
                    audit.add(acc["account_id"], "ACCOUNT_LOCK", "account", str(acc["account_id"]),
                              "Locked after too many failed logins", ip)
                    error = "Too many failed attempts. The account is locked; please contact the System Administrator."
            else:
                accounts.record_login_success(acc["account_id"])
                user = self._build_user(accounts, acc)
        # Loi duoc nem SAU khi transaction da commit de bo dem that bai duoc luu
        if error is not None:
            raise ServiceError(error)
        return user

    def _build_user(self, accounts, acc):
        roles = accounts.get_role_names(acc["account_id"])
        return {
            "account_id": acc["account_id"], "username": acc["username"], "full_name": acc["full_name"],
            "email": acc["email"], "roles": roles,
            "active_role": roles[0] if len(roles) > 0 else None,
            "must_change_password": bool(acc["must_change_password"]),
        }

    def _check_rate_limit(self, ip):
        if ip is None:
            return
        now = time.time()
        hits = []
        for stamp in AuthService._ip_hits.get(ip, []):
            if now - stamp < 60:
                hits.append(stamp)
        hits.append(now)
        AuthService._ip_hits[ip] = hits
        if len(hits) > 10:
            raise ServiceError("Too many login requests. Please try again in a minute.")

    # ------------------------------------------------------------------ UC02
    def logout(self, user, confirmed=True):
        """UC02: yeu cau xac nhan; neu nguoi dung quay lai thi giu nguyen phien."""
        return bool(confirmed)

    # ------------------------------------------------------------------ UC03
    def change_password(self, user, current_password, new_password, confirm_password):
        with self._db() as db:
            accounts = AccountRepo(db)
            acc = accounts.find_by_id(user["account_id"])
            if not verify_password(current_password or "", acc["password_hash"]):
                raise ServiceError("Current password is incorrect.")
            if new_password != confirm_password:
                raise ServiceError("The two entries of the new password do not match.")
            policy_error = check_password_policy(new_password or "")
            if policy_error:
                raise ServiceError(policy_error)
            if new_password == current_password:
                raise ServiceError("The new password must differ from the current password.")
            accounts.set_password(acc["account_id"], hash_password(new_password), 0)
        return True

    # ------------------------------------------------------------------ UC04
    def list_accounts(self, admin):
        require_role(admin, ROLE_ADMIN)
        with self._db() as db:
            accounts = AccountRepo(db)
            rows = accounts.list_all()
            for row in rows:
                row["roles"] = accounts.get_role_names(row["account_id"])
            return rows

    def create_account(self, admin, username, full_name, email, phone_number, role_names, ip=None):
        """UC04: tao tai khoan cho nhan vien quan ly; tra ve mat khau tam thoi de ban giao."""
        require_role(admin, ROLE_ADMIN)
        errors = {}
        username = (username or "").strip()
        if username == "" or len(username) > 50:
            errors["username"] = "Required (max 50 characters)."
        if (full_name or "").strip() == "":
            errors["full_name"] = "Required."
        if not is_valid_email(email):
            errors["email"] = "Invalid e-mail format."
        if not is_valid_phone(phone_number):
            errors["phone_number"] = "Invalid phone number."
        if not role_names:
            errors["roles"] = "Select at least one role (BR-01)."
        for role_name in role_names or []:
            if role_name not in STAFF_ROLES:
                errors["roles"] = "Lecturer and student accounts are created together with their profiles (UC05, UC06)."
        if errors:
            raise validation_error(errors)

        temp_password = generate_temp_password()
        with self._db() as db:
            accounts = AccountRepo(db)
            audit = AuditRepo(db)
            if accounts.find_by_username(username) is not None:
                raise ServiceError("Username already exists. Please choose a different username.",
                                   {"username": "Already exists."})  # BR-01
            if accounts.find_by_email(email) is not None:
                raise ServiceError("E-mail already exists.", {"email": "Already exists."})
            # BR-01: mot ho so - mot tai khoan, moi tai khoan co it nhat mot vai tro
            account_id = accounts.insert(username, hash_password(temp_password), full_name.strip(), email,
                                         phone_number or None, 1)
            accounts.insert_admin("AD%03d" % account_id, account_id)
            for role_name in role_names:
                accounts.add_role(account_id, accounts.get_role_id(role_name))
            audit.add(admin["account_id"], "ACCOUNT_CREATE", "account", str(account_id),
                      "roles=%s" % ",".join(role_names), ip)
        return {"account_id": account_id, "temporary_password": temp_password}

    def lock_account(self, admin, account_id, reason, confirmed=True, ip=None):
        require_role(admin, ROLE_ADMIN)
        if not confirmed:
            return False  # UC04.2.2: huy xac nhan -> khong doi
        if (reason or "").strip() == "":
            raise ServiceError("A reason is required to lock an account.")
        with self._db() as db:
            accounts = AccountRepo(db)
            target = accounts.find_by_id(account_id)
            if target is None:
                raise ServiceError("Account not found.")
            if target["account_id"] == admin["account_id"]:
                raise ServiceError("You cannot lock your own account.")
            roles = accounts.get_role_names(account_id)
            if ROLE_ADMIN in roles and target["status"] == "ACTIVE" and accounts.count_active_admins() <= 1:
                raise ServiceError("You cannot lock the last active System Administrator account.")
            accounts.set_status(account_id, "LOCKED")
            AuditRepo(db).add(admin["account_id"], "ACCOUNT_LOCK", "account", str(account_id), reason, ip)
        return True

    def unlock_account(self, admin, account_id, reason="", confirmed=True, ip=None):
        require_role(admin, ROLE_ADMIN)
        if not confirmed:
            return False
        with self._db() as db:
            accounts = AccountRepo(db)
            if accounts.find_by_id(account_id) is None:
                raise ServiceError("Account not found.")
            accounts.set_status(account_id, "ACTIVE")
            accounts.set_failed_attempts(account_id, 0)
            AuditRepo(db).add(admin["account_id"], "ACCOUNT_UNLOCK", "account", str(account_id), reason, ip)
        return True

    def reset_password(self, admin, account_id, confirmed=True, ip=None):
        """UC04: tao mat khau tam thoi moi, khong bao gio hien mat khau cu."""
        require_role(admin, ROLE_ADMIN)
        if not confirmed:
            return None
        temp_password = generate_temp_password()
        with self._db() as db:
            accounts = AccountRepo(db)
            if accounts.find_by_id(account_id) is None:
                raise ServiceError("Account not found.")
            accounts.set_password(account_id, hash_password(temp_password), 1)
            AuditRepo(db).add(admin["account_id"], "PASSWORD_RESET", "account", str(account_id), "Reset by admin", ip)
        return temp_password

    def assign_roles(self, admin, account_id, role_names, ip=None):
        """UC04: gan/thu hoi vai tro; khong cho bo vai tro SYSTEM_ADMIN cuoi cung."""
        require_role(admin, ROLE_ADMIN)
        if not role_names:
            raise ServiceError("Each account must keep at least one role (BR-01).")
        with self._db() as db:
            accounts = AccountRepo(db)
            if accounts.find_by_id(account_id) is None:
                raise ServiceError("Account not found.")
            wanted = []
            for role_name in role_names:
                role_id = accounts.get_role_id(role_name)
                if role_id is None:
                    raise ServiceError("Invalid role: %s." % role_name)
                wanted.append(role_id)
            old_roles = accounts.get_role_names(account_id)
            if ROLE_ADMIN in old_roles and ROLE_ADMIN not in role_names and accounts.count_active_admins() <= 1:
                raise ServiceError("This change would remove the last System Administrator role.")
            for role in accounts.list_roles():
                if role["role_id"] in wanted:
                    accounts.add_role(account_id, role["role_id"])
                elif role["role_name"] in old_roles:
                    accounts.remove_role(account_id, role["role_id"])
            AuditRepo(db).add(admin["account_id"], "ROLE_CHANGE", "account", str(account_id),
                              "old=%s new=%s" % (",".join(old_roles), ",".join(role_names)), ip)
        return True
