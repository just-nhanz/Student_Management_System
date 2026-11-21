from datetime import datetime

from app.repositories.base_repo import BaseRepo


class AuditRepo(BaseRepo):
    """BR-13 / NFR-SE-08: chi INSERT va SELECT, khong UPDATE/DELETE (append-only)."""

    def add(self, account_id, action, object_type=None, object_id=None, detail=None, ip_address=None):
        self.db.execute(
            "INSERT INTO audit_log (account_id, action, object_type, object_id, detail, ip_address, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (account_id, action, object_type, object_id, detail, ip_address, datetime.now()),
        )

    def list_by_action(self, action):
        return self.db.fetch_all(
            "SELECT * FROM audit_log WHERE action = %s ORDER BY log_id DESC", (action,))