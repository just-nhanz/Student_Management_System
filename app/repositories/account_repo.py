from datetime import datetime

from app.repositories.base_repo import BaseRepo


class AccountRepo(BaseRepo):
    """Bang account, role, account_role."""

    def find_by_username(self, username):
        return self.db.fetch_one("SELECT * FROM account WHERE username = %s", (username,))

    def find_by_id(self, account_id):
        return self.db.fetch_one("SELECT * FROM account WHERE account_id = %s", (account_id,))

    def find_by_email(self, email):
        return self.db.fetch_one("SELECT * FROM account WHERE email = %s", (email,))

    def list_all(self):
        return self.db.fetch_all(
            "SELECT account_id, username, full_name, email, phone_number, status, must_change_password "
            "FROM account ORDER BY account_id")

    def insert(self, username, password_hash, full_name, email, phone_number, must_change_password=1):
        _, new_id = self.db.execute(
            "INSERT INTO account (username, password_hash, full_name, email, phone_number, status, "
            "failed_attempts, must_change_password, created_at) VALUES (%s, %s, %s, %s, %s, 'ACTIVE', 0, %s, %s)",
            (username, password_hash, full_name, email, phone_number, must_change_password, datetime.now()))
        return new_id

    def update_contact(self, account_id, full_name, email, phone_number):
        self.db.execute(
            "UPDATE account SET full_name = %s, email = %s, phone_number = %s WHERE account_id = %s",
            (full_name, email, phone_number, account_id))

    def set_status(self, account_id, status):
        self.db.execute("UPDATE account SET status = %s WHERE account_id = %s", (status, account_id))

    def set_failed_attempts(self, account_id, count):
        self.db.execute("UPDATE account SET failed_attempts = %s WHERE account_id = %s", (count, account_id))

    def record_login_success(self, account_id):
        self.db.execute(
            "UPDATE account SET failed_attempts = 0, last_login_at = %s WHERE account_id = %s",
            (datetime.now(), account_id))

    def set_password(self, account_id, password_hash, must_change_password):
        self.db.execute(
            "UPDATE account SET password_hash = %s, must_change_password = %s WHERE account_id = %s",
            (password_hash, must_change_password, account_id))

    # ---- vai tro ----
    def get_role_names(self, account_id):
        rows = self.db.fetch_all(
            "SELECT r.role_name FROM role r JOIN account_role ar ON ar.role_id = r.role_id "
            "WHERE ar.account_id = %s ORDER BY r.role_id", (account_id,))
        names = []
        for row in rows:
            names.append(row["role_name"])
        return names

    def get_role_id(self, role_name):
        row = self.db.fetch_one("SELECT role_id FROM role WHERE role_name = %s", (role_name,))
        if row is None:
            return None
        return row["role_id"]

    def list_roles(self):
        return self.db.fetch_all("SELECT role_id, role_name FROM role ORDER BY role_id")

    def add_role(self, account_id, role_id):
        self.db.execute(
            "INSERT IGNORE INTO account_role (account_id, role_id) VALUES (%s, %s)", (account_id, role_id))

    def remove_role(self, account_id, role_id):
        self.db.execute(
            "DELETE FROM account_role WHERE account_id = %s AND role_id = %s", (account_id, role_id))

    def count_active_admins(self):
        row = self.db.fetch_one(
            "SELECT COUNT(*) AS total FROM account a JOIN account_role ar ON ar.account_id = a.account_id "
            "JOIN role r ON r.role_id = ar.role_id WHERE r.role_name = 'SYSTEM_ADMIN' AND a.status = 'ACTIVE'")
        return row["total"]

    # ---- ho so admin ----
    def insert_admin(self, admin_id, account_id):
        self.db.execute("INSERT INTO admin (admin_id, account_id) VALUES (%s, %s)", (admin_id, account_id))