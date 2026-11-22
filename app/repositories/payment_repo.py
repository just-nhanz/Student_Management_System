from datetime import datetime

from app.repositories.base_repo import BaseRepo


class PaymentRepo(BaseRepo):
    """Bang tuition_rate, waiver_policy, student_waiver, student_debt, payment_transaction (UC14 - UC19)."""

    # ---------- tuition_rate ----------
    def insert_rate(self, major_id, semester_id, academic_year, price_per_credit, effective_from, effective_to):
        _, new_id = self.db.execute(
            "INSERT INTO tuition_rate (major_id, semester_id, academic_year, price_per_credit, effective_from, "
            "effective_to) VALUES (%s, %s, %s, %s, %s, %s)",
            (major_id, semester_id, academic_year, price_per_credit, effective_from, effective_to))
        return new_id

    def list_rates(self):
        return self.db.fetch_all(
            "SELECT * FROM tuition_rate ORDER BY semester_id DESC, major_id, effective_from DESC")

    def find_overlapping_rates(self, major_id, semester_id, academic_year, effective_from, effective_to):
        far_future = "9999-12-31"
        return self.db.fetch_all(
            "SELECT * FROM tuition_rate WHERE major_id = %s AND semester_id = %s "
            "AND ((academic_year IS NULL AND %s IS NULL) OR academic_year = %s) "
            "AND effective_from <= COALESCE(%s, %s) AND COALESCE(effective_to, %s) >= %s",
            (major_id, semester_id, academic_year, academic_year, effective_to, far_future, far_future,
             effective_from))

    def find_rate(self, major_id, semester_id, academic_year, on_date):
        """Uu tien muc gia rieng cho khoa (academic_year), sau do den muc gia chung (NULL)."""
        return self.db.fetch_one(
            "SELECT * FROM tuition_rate WHERE major_id = %s AND semester_id = %s "
            "AND (academic_year IS NULL OR academic_year = %s) AND effective_from <= %s "
            "AND (effective_to IS NULL OR effective_to >= %s) "
            "ORDER BY (academic_year IS NULL), effective_from DESC LIMIT 1",
            (major_id, semester_id, academic_year, on_date, on_date))

    # ---------- waiver ----------
    def insert_policy(self, policy_name, policy_type, value_type, value, conditions, valid_from, valid_to):
        _, new_id = self.db.execute(
            "INSERT INTO waiver_policy (policy_name, policy_type, value_type, value, conditions, valid_from, "
            "valid_to) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (policy_name, policy_type, value_type, value, conditions, valid_from, valid_to))
        return new_id

    def find_policy(self, policy_id):
        return self.db.fetch_one("SELECT * FROM waiver_policy WHERE policy_id = %s", (policy_id,))

    def list_policies(self):
        return self.db.fetch_all("SELECT * FROM waiver_policy ORDER BY policy_id DESC")

    def find_student_waiver(self, student_id, policy_id, semester_id):
        return self.db.fetch_one(
            "SELECT * FROM student_waiver WHERE student_id = %s AND policy_id = %s AND semester_id = %s",
            (student_id, policy_id, semester_id))

    def insert_student_waiver(self, student_id, policy_id, semester_id, basis, granted_by):
        self.db.execute(
            "INSERT INTO student_waiver (student_id, policy_id, semester_id, basis, granted_by, granted_at) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (student_id, policy_id, semester_id, basis, granted_by, datetime.now()))

    def list_student_waivers(self, student_id, semester_id):
        """Chi lay chinh sach con hieu luc trong hoc ky (khong ap dung chinh sach het han)."""
        return self.db.fetch_all(
            "SELECT p.* FROM student_waiver w JOIN waiver_policy p ON p.policy_id = w.policy_id "
            "JOIN semester sm ON sm.semester_id = w.semester_id "
            "WHERE w.student_id = %s AND w.semester_id = %s AND p.valid_from <= sm.end_date "
            "AND p.valid_to >= sm.start_date", (student_id, semester_id))

    # ---------- student_debt ----------
    def find_debt(self, student_id, semester_id):
        return self.db.fetch_one(
            "SELECT * FROM student_debt WHERE student_id = %s AND semester_id = %s", (student_id, semester_id))

    def find_debt_for_update(self, student_id, semester_id):
        return self.db.fetch_one(
            "SELECT * FROM student_debt WHERE student_id = %s AND semester_id = %s FOR UPDATE",
            (student_id, semester_id))

    def find_debt_by_id(self, debt_id):
        return self.db.fetch_one("SELECT * FROM student_debt WHERE debt_id = %s", (debt_id,))

    def insert_debt(self, student_id, semester_id, total_payable, amount_paid, due_date, status):
        _, new_id = self.db.execute(
            "INSERT INTO student_debt (student_id, semester_id, total_payable, amount_paid, due_date, status) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (student_id, semester_id, total_payable, amount_paid, due_date, status))
        return new_id

    def update_debt(self, debt_id, total_payable, amount_paid, status):
        self.db.execute(
            "UPDATE student_debt SET total_payable = %s, amount_paid = %s, status = %s WHERE debt_id = %s",
            (total_payable, amount_paid, status, debt_id))

    def list_debts_of_student(self, student_id):
        return self.db.fetch_all(
            "SELECT d.*, sm.semester_name FROM student_debt d JOIN semester sm ON sm.semester_id = d.semester_id "
            "WHERE d.student_id = %s ORDER BY sm.start_date DESC", (student_id,))

    def sum_overdue_debt(self, student_id, today):
        """BR-08: tong no qua han cua sinh vien."""
        row = self.db.fetch_one(
            "SELECT COALESCE(SUM(remaining_debt), 0) AS total FROM student_debt "
            "WHERE student_id = %s AND remaining_debt > 0 AND due_date < %s", (student_id, today))
        return row["total"]

    def list_overdue(self, semester_id, faculty_id, class_id, major_id, overdue_before, offset, limit):
        sql = ("SELECT d.debt_id, d.student_id, a.full_name, s.class_id, c.major_id, m.faculty_id, d.semester_id, "
               "d.total_payable, d.amount_paid, d.remaining_debt, d.due_date FROM student_debt d "
               "JOIN student s ON s.student_id = d.student_id JOIN account a ON a.account_id = s.account_id "
               "JOIN administrative_class c ON c.class_id = s.class_id JOIN major m ON m.major_id = c.major_id "
               "WHERE d.remaining_debt > 0 AND d.due_date < %s")
        params = [overdue_before]
        sql, params = self._overdue_filters(sql, params, semester_id, faculty_id, class_id, major_id)
        sql += " ORDER BY d.due_date, d.student_id LIMIT %s OFFSET %s"
        params.append(limit)
        params.append(offset)
        return self.db.fetch_all(sql, tuple(params))

    def count_overdue(self, semester_id, faculty_id, class_id, major_id, overdue_before):
        sql = ("SELECT COUNT(*) AS total FROM student_debt d JOIN student s ON s.student_id = d.student_id "
               "JOIN administrative_class c ON c.class_id = s.class_id JOIN major m ON m.major_id = c.major_id "
               "WHERE d.remaining_debt > 0 AND d.due_date < %s")
        params = [overdue_before]
        sql, params = self._overdue_filters(sql, params, semester_id, faculty_id, class_id, major_id)
        return self.db.fetch_one(sql, tuple(params))["total"]

    def _overdue_filters(self, sql, params, semester_id, faculty_id, class_id, major_id):
        if semester_id:
            sql += " AND d.semester_id = %s"
            params.append(semester_id)
        if faculty_id:
            sql += " AND m.faculty_id = %s"
            params.append(faculty_id)
        if class_id:
            sql += " AND s.class_id = %s"
            params.append(class_id)
        if major_id:
            sql += " AND c.major_id = %s"
            params.append(major_id)
        return sql, params

    # ---------- payment_transaction (chi INSERT, rieng PENDING -> CONFIRMED duoc UPDATE) ----------
    def insert_transaction(self, reference_code, debt_id, transaction_type, amount, method, status,
                           received_by, original_transaction_id, reason):
        _, new_id = self.db.execute(
            "INSERT INTO payment_transaction (reference_code, debt_id, transaction_type, amount, method, status, "
            "transaction_time, received_by, original_transaction_id, reason) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (reference_code, debt_id, transaction_type, amount, method, status, datetime.now(), received_by,
             original_transaction_id, reason))
        return new_id

    def confirm_transaction(self, transaction_id, receipt_no):
        self.db.execute(
            "UPDATE payment_transaction SET status = 'CONFIRMED', receipt_no = %s "
            "WHERE transaction_id = %s AND status = 'PENDING'", (receipt_no, transaction_id))

    def find_transaction(self, transaction_id):
        return self.db.fetch_one("SELECT * FROM payment_transaction WHERE transaction_id = %s", (transaction_id,))

    def find_by_reference(self, reference_code):
        return self.db.fetch_one(
            "SELECT * FROM payment_transaction WHERE reference_code = %s", (reference_code,))

    def list_by_student(self, student_id, semester_id=None):
        sql = ("SELECT t.*, d.semester_id, d.student_id FROM payment_transaction t "
               "JOIN student_debt d ON d.debt_id = t.debt_id WHERE d.student_id = %s")
        params = [student_id]
        if semester_id:
            sql += " AND d.semester_id = %s"
            params.append(semester_id)
        sql += " ORDER BY t.transaction_time DESC, t.transaction_id DESC"
        return self.db.fetch_all(sql, tuple(params))

    def sum_ledger(self, debt_id):
        """So tien da thu (PAYMENT - REFUND, da CONFIRMED) va tong dieu chinh giam (ADJUSTMENT) cua mot khoan no."""
        return self.db.fetch_one(
            "SELECT COALESCE(SUM(CASE WHEN transaction_type = 'PAYMENT' AND status = 'CONFIRMED' THEN amount "
            "WHEN transaction_type = 'REFUND' AND status = 'CONFIRMED' THEN -amount ELSE 0 END), 0) AS paid, "
            "COALESCE(SUM(CASE WHEN transaction_type = 'ADJUSTMENT' AND status = 'CONFIRMED' THEN amount "
            "ELSE 0 END), 0) AS adjusted FROM payment_transaction WHERE debt_id = %s", (debt_id,))

    def sum_linked_refunds(self, original_transaction_id):
        row = self.db.fetch_one(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM payment_transaction "
            "WHERE original_transaction_id = %s AND transaction_type = 'REFUND'", (original_transaction_id,))
        return row["total"]

    def count_receipt_prints(self, transaction_id):
        row = self.db.fetch_one(
            "SELECT COUNT(*) AS total FROM audit_log WHERE action = 'RECEIPT_PRINT' AND object_id = %s",
            (str(transaction_id),))
        return row["total"]

