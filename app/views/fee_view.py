from tkinter import messagebox, ttk

from app.gui.components.widgets import (DataTable, FormFields, Pager, acting_user, confirm, open_html, run,
                                        show_system_error)
from app.services import ServiceError
from app.services.catalog_service import CatalogService
from app.services.fee_service import FeeService
from app.utils.export_handler import receipt_html


class TuitionSetupView(ttk.Frame):
    """UC14: don gia tin chi, chinh sach mien giam / hoc bong, gan cho sinh vien."""

    def __init__(self, parent, user):
        super().__init__(parent, padding=10)
        self.user = acting_user(user)
        self.service = FeeService()
        major_ids = []
        semester_ids = []
        catalog, failed = run(lambda: CatalogService().list_all({"roles": ["TRAINING_MANAGER"]}))
        if not failed:
            major_ids = [row["major_id"] for row in catalog["majors"]]
            semester_ids = [row["semester_id"] for row in catalog["semesters"]]

        ttk.Label(self, text="Tuition rates").pack(anchor="w")
        self.rates = DataTable(self, ("major_id", "semester_id", "academic_year", "price_per_credit",
                                      "effective_from", "effective_to"), height=4)
        self.rates.pack(fill="both", expand=True)
        self.rate_form = FormFields(self, [
            ("major_id", "Major ID", major_ids), ("semester_id", "Semester ID", semester_ids),
            ("academic_year", "Cohort year (optional)"), ("price", "Price per credit"),
            ("effective_from", "From (YYYY-MM-DD)"), ("effective_to", "To (optional)")])
        self.rate_form.pack(pady=4)
        ttk.Button(self, text="Save rate", command=self.save_rate).pack()

        ttk.Label(self, text="Waiver / scholarship policies").pack(anchor="w", pady=(8, 0))
        self.policies = DataTable(self, ("policy_id", "policy_name", "policy_type", "value_type", "value",
                                         "valid_from", "valid_to"), height=4)
        self.policies.pack(fill="both", expand=True)
        self.policy_form = FormFields(self, [
            ("policy_name", "Name"), ("policy_type", "Type", ["WAIVER", "SCHOLARSHIP"]),
            ("value_type", "Value type", ["PERCENT", "AMOUNT"]), ("value", "Value"),
            ("conditions", "Conditions"), ("valid_from", "Valid from (YYYY-MM-DD)"),
            ("valid_to", "Valid to (YYYY-MM-DD)")])
        self.policy_form.pack(pady=4)
        ttk.Button(self, text="Create policy", command=self.create_policy).pack()

        self.assign_form = FormFields(self, [
            ("student_id", "Student ID"), ("policy_id", "Policy ID"),
            ("semester_id", "Semester ID", semester_ids), ("basis", "Basis / decision")])
        self.assign_form.pack(pady=4)
        ttk.Button(self, text="Assign policy to student", command=self.assign).pack()
        self.refresh()

    def refresh(self):
        rates, failed = run(lambda: self.service.list_rates(self.user))
        if not failed:
            self.rates.load(rates)
        policies, failed = run(lambda: self.service.list_policies(self.user))
        if not failed:
            self.policies.load(policies)

    def save_rate(self):
        v = self.rate_form.get()
        args = (self.user, v["major_id"], v["semester_id"], v["academic_year"] or None, v["price"],
                v["effective_from"], v["effective_to"] or None)
        try:
            self.service.set_rate(*args, False)
            messagebox.showinfo("Success", "Rate saved.")
        except ServiceError as error:
            if error.message.startswith("Warning: an overlapping rate"):
                # UC14.2.2: canh bao trung khoang hieu luc - xac nhan moi luu
                if confirm(error.message + "\n\nSave anyway?"):
                    run(lambda: self.service.set_rate(*args, True), "Rate saved.")
            else:
                messagebox.showerror("Error", error.message)
        except Exception:
            show_system_error()
        self.refresh()

    def create_policy(self):
        v = self.policy_form.get()
        _, failed = run(lambda: self.service.create_policy(
            self.user, v["policy_name"], v["policy_type"], v["value_type"], v["value"], v["conditions"],
            v["valid_from"], v["valid_to"]), "Policy created.")
        self.refresh()

    def assign(self):
        v = self.assign_form.get()
        try:
            policy_id = int(v["policy_id"])
        except ValueError:
            messagebox.showerror("Error", "Policy ID must be a number.")
            return
        run(lambda: self.service.assign_waiver(self.user, v["student_id"], policy_id, v["semester_id"], v["basis"]),
            "Waiver assigned.")


class CollectFeeView(ttk.Frame):
    """UC15 (thu hoc phi) va UC16 (in bien lai)."""

    def __init__(self, parent, user):
        super().__init__(parent, padding=10)
        self.user = acting_user(user)
        self.service = FeeService()
        self.current_student = ""
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Student ID").pack(side="left")
        self.student_id = ttk.Entry(top, width=16)
        self.student_id.pack(side="left", padx=4)
        ttk.Button(top, text="Search", command=self.search).pack(side="left")
        self.debts = DataTable(self, ("semester_id", "total_payable", "amount_paid", "remaining_debt",
                                      "due_date", "status"), height=4)
        self.debts.pack(fill="both", expand=True, pady=4)
        self.txns = DataTable(self, ("transaction_id", "reference_code", "transaction_type", "amount", "method",
                                     "status", "receipt_no"), height=6)
        self.txns.pack(fill="both", expand=True)
        self.form = FormFields(self, [
            ("semester_id", "Semester ID", []), ("amount", "Amount"),
            ("method", "Method", ["CASH", "BANK_TRANSFER"]), ("reference_code", "Reference (optional)"),
            ("bank_verified", "Bank transfer verified", ["No", "Yes"])])
        self.form.pack(pady=4)
        buttons = ttk.Frame(self)
        buttons.pack()
        for text, command in [("Record payment", self.pay), ("Confirm selected transfer", self.confirm_transfer),
                              ("Print receipt", self.print_receipt)]:
            ttk.Button(buttons, text=text, command=command).pack(side="left", padx=4)

    def search(self):
        self.current_student = self.student_id.get().strip()
        info, failed = run(lambda: self.service.lookup_student(self.user, self.current_student))
        if failed:
            return
        self.debts.load(info["debts"])
        self.txns.load(info["transactions"])
        self.form.set_choices("semester_id", [row["semester_id"] for row in info["debts"]])
        if len(info["debts"]) == 0:
            messagebox.showinfo("Tuition", "No tuition data exists for this student.")

    def pay(self):
        v = self.form.get()
        if not confirm("Record this payment?"):
            return
        _, failed = run(lambda: self.service.collect_payment(
            self.user, self.current_student, v["semester_id"], v["amount"], v["method"],
            v["reference_code"] or None, v["bank_verified"] == "Yes"), "Payment recorded.")
        self.search()

    def confirm_transfer(self):
        row = self.txns.selected()
        if row is None:
            messagebox.showinfo("Select", "Please select a PENDING transfer.")
            return
        _, failed = run(lambda: self.service.confirm_transfer(self.user, row["transaction_id"]), "Transfer confirmed.")
        self.search()

    def print_receipt(self):
        row = self.txns.selected()
        if row is None:
            messagebox.showinfo("Select", "Please select a transaction.")
            return
        data, failed = run(lambda: self.service.print_receipt(self.user, row["transaction_id"]))
        if not failed:
            open_html(receipt_html(data["transaction"], data["student"], data["is_copy"]),
                      "sms_receipt_%s.html" % row["transaction_id"])


class DebtRefundView(ttk.Frame):
    """UC18 (cong no, no qua han) va UC19 (hoan tien / dieu chinh)."""

    def __init__(self, parent, user):
        super().__init__(parent, padding=10)
        self.user = acting_user(user)
        self.service = FeeService()
        self.page = 1

        lookup = ttk.LabelFrame(self, text="Student debts and payment history", padding=6)
        lookup.pack(fill="x")
        row = ttk.Frame(lookup)
        row.pack(fill="x")
        ttk.Label(row, text="Student ID").pack(side="left")
        self.student_id = ttk.Entry(row, width=16)
        self.student_id.pack(side="left", padx=4)
        ttk.Button(row, text="Look up", command=self.lookup).pack(side="left")
        self.debts = DataTable(lookup, ("semester_id", "total_payable", "amount_paid", "remaining_debt",
                                        "due_date", "status"), height=3)
        self.debts.pack(fill="x", pady=2)
        self.txns = DataTable(lookup, ("transaction_id", "reference_code", "transaction_type", "amount", "status",
                                       "original_transaction_id", "reason"), height=4)
        self.txns.pack(fill="x")
        self.refund_form = FormFields(lookup, [
            ("transaction_id", "Original transaction ID"), ("kind", "Kind", ["REFUND", "ADJUSTMENT"]),
            ("amount", "Amount"), ("method", "Method", ["CASH", "BANK_TRANSFER"]),
            ("reason", "Reason"), ("basis", "Basis"), ("approver", "Approver")])
        self.refund_form.pack(pady=4)
        ttk.Button(lookup, text="Submit refund / adjustment", command=self.submit).pack()

        overdue = ttk.LabelFrame(self, text="Overdue debts", padding=6)
        overdue.pack(fill="both", expand=True, pady=6)
        self.filter_form = FormFields(overdue, [
            ("semester_id", "Semester ID"), ("faculty_id", "Faculty ID"), ("major_id", "Major ID"),
            ("class_id", "Class ID"), ("overdue_before", "Overdue before (YYYY-MM-DD)")], columns=3, width=16)
        self.filter_form.pack()
        ttk.Button(overdue, text="Filter", command=lambda: self.overdue(1)).pack(pady=2)
        self.overdue_table = DataTable(overdue, ("student_id", "full_name", "class_id", "semester_id",
                                                 "remaining_debt", "due_date"), height=6)
        self.overdue_table.pack(fill="both", expand=True)
        self.pager = Pager(overdue, self.overdue)
        self.pager.pack()
        self.overdue(1)

    def lookup(self):
        info, failed = run(lambda: self.service.lookup_student(self.user, self.student_id.get().strip()))
        if not failed:
            self.debts.load(info["debts"])
            self.txns.load(info["transactions"])

    def submit(self):
        v = self.refund_form.get()
        try:
            transaction_id = int(v["transaction_id"])
        except ValueError:
            messagebox.showerror("Error", "Original transaction ID must be a number.")
            return
        if confirm("Record this refund / adjustment?"):
            _, failed = run(lambda: self.service.refund_or_adjust(
                self.user, transaction_id, v["kind"], v["amount"], v["reason"], v["basis"],
                v["method"] or "CASH", v["approver"]), "Refund / adjustment recorded.")
            if not failed and self.student_id.get().strip() != "":
                self.lookup()

    def overdue(self, page=None):
        if page is not None:
            self.page = page
        v = self.filter_form.get()
        info, failed = run(lambda: self.service.overdue_list(
            self.user, v["semester_id"], v["faculty_id"], v["class_id"], v["major_id"],
            v["overdue_before"] or None, self.page))
        if not failed:
            self.overdue_table.load(info["rows"])
            self.pager.update_info(info["page"], info["pages"])


class MyTuitionView(ttk.Frame):
    """UC17: sinh vien xem cong no va lich su thanh toan cua chinh minh."""

    def __init__(self, parent, user):
        super().__init__(parent, padding=10)
        self.user = acting_user(user)
        self.debts = DataTable(self, ("semester_id", "total_payable", "amount_paid", "remaining_debt",
                                      "due_date", "status"))
        self.debts.pack(fill="both", expand=True)
        self.txns = DataTable(self, ("transaction_id", "transaction_time", "transaction_type", "amount",
                                     "method", "status"))
        self.txns.pack(fill="both", expand=True, pady=6)
        ttk.Button(self, text="Refresh", command=self.refresh).pack()
        self.refresh()

    def refresh(self):
        data, failed = run(lambda: FeeService().student_status(self.user))
        if not failed:
            self.debts.load(data["debts"])
            self.txns.load(data["transactions"])

