import time
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from app.config import ROLE_FINANCE, ROLE_STUDENT
from app.repositories.audit_repo import AuditRepo
from app.repositories.catalog_repo import CatalogRepo
from app.repositories.enroll_repo import EnrollRepo
from app.repositories.payment_repo import PaymentRepo
from app.repositories.user_repo import UserRepo
from app.services import (PermissionDenied, ServiceError, page_info, parse_date, require_role, validation_error)
from app.utils.database import Database

TWO = Decimal("0.01")


def to_money(value, field_name):
    """Chuyen chuoi/so sang Decimal 2 chu so; bao loi neu khong hop le."""
    try:
        amount = Decimal(str(value).strip()).quantize(TWO, rounding=ROUND_HALF_UP)
    except Exception:
        raise validation_error({field_name: "Invalid number."})
    return amount


class FeeService:
    """UC14 - UC19: hoc phi, mien giam, thu tien, bien lai, cong no, hoan tien/dieu chinh."""

    def __init__(self, connection=None):
        self.connection = connection

    def _db(self):
        return Database(self.connection)

    # ------------------------------------------------------------------ BR-11
    @staticmethod
    def calc_status(total, paid, due_date):
        """DebtStatus: OVERDUE khi qua han va con no; COMPLETED khi het no."""
        remaining = total - paid
        if remaining <= 0:
            return "COMPLETED"
        if due_date < date.today():
            return "OVERDUE"
        if paid > 0:
            return "PARTIALLY_PAID"
        return "UNPAID"

    def recalculate_debt(self, db, student_id, semester_id):
        """UC10/UC11/UC14/UC19 - BR-11: hoc phi = SUM(tin chi x don gia) - mien giam (- dieu chinh).
        Duoc EnrollService goi trong CUNG transaction voi dang ky / huy dang ky."""
        users = UserRepo(db)
        enroll = EnrollRepo(db)
        catalog = CatalogRepo(db)
        pay = PaymentRepo(db)
        semester = catalog.find_semester(semester_id)
        student = users.find_student(student_id)
        class_row = catalog.find_class(student["class_id"])
        major_id = enroll.find_student_major(student_id)
        rate = pay.find_rate(major_id, semester_id, class_row["academic_year"], date.today())
        if rate is None:
            raise ServiceError("No tuition rate is configured for this major and semester.")
        gross = Decimal(enroll.sum_credits(student_id, semester_id)) * rate["price_per_credit"]
        # Mien giam / hoc bong con hieu luc trong hoc ky
        waiver_total = Decimal("0")
        for policy in pay.list_student_waivers(student_id, semester_id):
            if policy["value_type"] == "PERCENT":
                waiver_total += (gross * policy["value"] / Decimal("100")).quantize(TWO, rounding=ROUND_HALF_UP)
            else:
                waiver_total += policy["value"]
        if waiver_total > gross:
            waiver_total = gross
        debt = pay.find_debt_for_update(student_id, semester_id)
        if debt is None:
            total = gross - waiver_total
            status = self.calc_status(total, Decimal("0"), semester["start_date"])
            debt_id = pay.insert_debt(student_id, semester_id, total, Decimal("0"), semester["start_date"], status)
            return pay.find_debt_by_id(debt_id)
        ledger = pay.sum_ledger(debt["debt_id"])
        total = gross - waiver_total - ledger["adjusted"]
        if total < 0:
            total = Decimal("0")
        status = self.calc_status(total, ledger["paid"], debt["due_date"])
        pay.update_debt(debt["debt_id"], total, ledger["paid"], status)
        return pay.find_debt_by_id(debt["debt_id"])

    # ------------------------------------------------------------------ UC14
    def set_rate(self, actor, major_id, semester_id, academic_year, price, effective_from, effective_to=None,
                 confirm_overlap=False):
        require_role(actor, ROLE_FINANCE)
        errors = {}
        price = to_money(price, "price_per_credit") if str(price).strip() != "" else None
        if price is None or price <= 0:
            errors["price_per_credit"] = "Must be greater than 0."
        if (major_id or "") == "" or (semester_id or "") == "":
            errors["scope"] = "Major and semester are required."
        if errors:
            raise validation_error(errors)
        start = parse_date(effective_from, "effective_from")
        end = parse_date(effective_to, "effective_to") if effective_to else None
        if end is not None and end < start:
            raise ServiceError("The end of the effective period must not be before its start.")
        with self._db() as db:
            catalog = CatalogRepo(db)
            pay = PaymentRepo(db)
            if catalog.find_major(major_id) is None or catalog.find_semester(semester_id) is None:
                raise ServiceError("Major or semester does not exist.")
            overlaps = pay.find_overlapping_rates(major_id, semester_id, academic_year or None, start, end)
            if len(overlaps) > 0 and not confirm_overlap:
                # UC14.2.2: canh bao trung khoang hieu luc, yeu cau xac nhan
                raise ServiceError("Warning: an overlapping rate exists for the same scope. Confirm to continue.")
            rate_id = pay.insert_rate(major_id, semester_id, academic_year or None, price, start, end)
            AuditRepo(db).add(actor["account_id"], "TUITION_RATE_SET", "tuition_rate", str(rate_id),
                              "price=%s from=%s" % (price, start))
        return rate_id

    def list_rates(self, actor):
        require_role(actor, ROLE_FINANCE)
        with self._db() as db:
            return PaymentRepo(db).list_rates()

    def create_policy(self, actor, name, policy_type, value_type, value, conditions, valid_from, valid_to):
        require_role(actor, ROLE_FINANCE)
        errors = {}
        if (name or "").strip() == "":
            errors["policy_name"] = "Required."
        if policy_type not in ("WAIVER", "SCHOLARSHIP"):
            errors["policy_type"] = "Must be WAIVER or SCHOLARSHIP."
        if value_type not in ("PERCENT", "AMOUNT"):
            errors["value_type"] = "Must be PERCENT or AMOUNT."
        amount = to_money(value, "value")
        if amount <= 0 or (value_type == "PERCENT" and amount > 100):
            errors["value"] = "Invalid amount or percentage."
        start = parse_date(valid_from, "valid_from")
        end = parse_date(valid_to, "valid_to")
        if end < start:
            errors["valid_to"] = "Must not be before the start date."
        if errors:
            raise validation_error(errors)
        with self._db() as db:
            policy_id = PaymentRepo(db).insert_policy(name.strip(), policy_type, value_type, amount,
                                                      conditions or None, start, end)
            AuditRepo(db).add(actor["account_id"], "WAIVER_POLICY_CREATE", "waiver_policy", str(policy_id), None)
        return policy_id

    def list_policies(self, actor):
        require_role(actor, ROLE_FINANCE)
        with self._db() as db:
            return PaymentRepo(db).list_policies()

    def assign_waiver(self, actor, student_id, policy_id, semester_id, basis):
        """UC14: ghi nhan sinh vien duoc mien giam / hoc bong, sau do tinh lai hoc phi (BR-11)."""
        require_role(actor, ROLE_FINANCE)
        if (basis or "").strip() == "":
            raise validation_error({"basis": "Required."})
        with self._db() as db:
            pay = PaymentRepo(db)
            if UserRepo(db).find_student(student_id) is None:
                raise ServiceError("Student does not exist.")
            policy = pay.find_policy(policy_id)
            semester = CatalogRepo(db).find_semester(semester_id)
            if policy is None or semester is None:
                raise ServiceError("Policy or semester does not exist.")
            # UC14.2.2: khong ap dung chinh sach het han cho hoc ky ngoai thoi han
            if policy["valid_to"] < semester["start_date"] or policy["valid_from"] > semester["end_date"]:
                raise ServiceError("The policy is not valid in this semester.")
            if pay.find_student_waiver(student_id, policy_id, semester_id) is not None:
                raise ServiceError("The student already has this policy for the semester.")
            pay.insert_student_waiver(student_id, policy_id, semester_id, basis.strip(), actor["account_id"])
            AuditRepo(db).add(actor["account_id"], "WAIVER_ASSIGN", "student", student_id,
                              "policy=%s semester=%s" % (policy_id, semester_id))
            if pay.find_debt(student_id, semester_id) is not None:
                self.recalculate_debt(db, student_id, semester_id)
        return True

    # ------------------------------------------------------------------ UC15
    def collect_payment(self, actor, student_id, semester_id, amount, method, reference_code=None,
                        bank_verified=False, ip=None):
        """UC15: ghi nhan thu hoc phi; chuyen khoan chua xac minh -> PENDING."""
        require_role(actor, ROLE_FINANCE)
        amount = to_money(amount, "amount")
        if amount <= 0:
            raise ServiceError("The payment amount must be greater than 0.")
        if method not in ("CASH", "BANK_TRANSFER"):
            raise ServiceError("Invalid payment method.")
        reference_code = (reference_code or "").strip()
        if reference_code == "":
            reference_code = "PAY-%s-%d" % (datetime.now().strftime("%Y%m%d%H%M%S"), int(time.time() * 1000) % 100000)
        with self._db() as db:
            pay = PaymentRepo(db)
            if UserRepo(db).find_student(student_id) is None:
                raise ServiceError("Student does not exist.")
            debt = pay.find_debt_for_update(student_id, semester_id)
            if debt is None:
                raise ServiceError("The student has no tuition data for this semester.")
            if pay.find_by_reference(reference_code) is not None:
                raise ServiceError("Duplicate transaction: this reference code was already recorded.")
            status = "CONFIRMED" if (method == "CASH" or bank_verified) else "PENDING"
            txn_id = pay.insert_transaction(reference_code, debt["debt_id"], "PAYMENT", amount, method, "PENDING",
                                            actor["account_id"], None, None)
            if status == "CONFIRMED":
                pay.confirm_transaction(txn_id, "RC%08d" % txn_id)
            AuditRepo(db).add(actor["account_id"], "PAYMENT", "payment_transaction", str(txn_id),
                              "amount=%s method=%s status=%s" % (amount, method, status), ip)
            self.recalculate_debt(db, student_id, semester_id)
        return {"transaction_id": txn_id, "reference_code": reference_code, "status": status}

    def confirm_transfer(self, actor, transaction_id, ip=None):
        """UC15.2.2: xac nhan chuyen khoan (PENDING -> CONFIRMED) roi moi tinh la da thu."""
        require_role(actor, ROLE_FINANCE)
        with self._db() as db:
            pay = PaymentRepo(db)
            txn = pay.find_transaction(transaction_id)
            if txn is None or txn["status"] != "PENDING":
                raise ServiceError("Pending transaction not found.")
            pay.confirm_transaction(transaction_id, "RC%08d" % transaction_id)
            debt = pay.find_debt_by_id(txn["debt_id"])
            self.recalculate_debt(db, debt["student_id"], debt["semester_id"])
            AuditRepo(db).add(actor["account_id"], "PAYMENT_CONFIRM", "payment_transaction", str(transaction_id), None, ip)
        return True

    # ------------------------------------------------------------------ UC16
    def print_receipt(self, actor, transaction_id):
        """UC16: khong in bien lai chinh thuc cho giao dich chua xac nhan; in lai danh dau la ban sao."""
        require_role(actor, ROLE_FINANCE)
        with self._db() as db:
            pay = PaymentRepo(db)
            txn = pay.find_transaction(transaction_id)
            if txn is None:
                raise ServiceError("Transaction not found.")
            if txn["status"] != "CONFIRMED" or txn["transaction_type"] != "PAYMENT":
                raise ServiceError("An official receipt cannot be issued for an unconfirmed transaction.")
            debt = pay.find_debt_by_id(txn["debt_id"])
            student = UserRepo(db).find_student(debt["student_id"])
            is_copy = pay.count_receipt_prints(transaction_id) > 0
            AuditRepo(db).add(actor["account_id"], "RECEIPT_PRINT", "payment_transaction", str(transaction_id),
                              "copy" if is_copy else "original")
            return {"transaction": txn, "student": student, "is_copy": is_copy}

    # ------------------------------------------------------------------ UC17
    def student_status(self, user, student_id=None):
        """UC17: sinh vien chi xem tai chinh cua chinh minh (NFR-SE-02)."""
        require_role(user, ROLE_STUDENT)
        with self._db() as db:
            users = UserRepo(db)
            own = users.find_student_by_account(user["account_id"])
            if own is None:
                raise ServiceError("Student profile not found.")
            if student_id is not None and student_id != own["student_id"]:
                raise PermissionDenied("You can only view your own tuition data.")
            pay = PaymentRepo(db)
            return {"student": own, "debts": pay.list_debts_of_student(own["student_id"]),
                    "transactions": pay.list_by_student(own["student_id"])}

    # ------------------------------------------------------------------ UC18
    def lookup_student(self, actor, student_id):
        require_role(actor, ROLE_FINANCE)
        with self._db() as db:
            users = UserRepo(db)
            pay = PaymentRepo(db)
            student = users.find_student(student_id)
            if student is None:
                raise ServiceError("Student not found.")
            return {"student": student, "debts": pay.list_debts_of_student(student_id),
                    "transactions": pay.list_by_student(student_id)}

    def overdue_list(self, actor, semester_id="", faculty_id="", class_id="", major_id="", overdue_before=None, page=1):
        require_role(actor, ROLE_FINANCE)
        before = parse_date(overdue_before, "overdue_before") if overdue_before else date.today()
        with self._db() as db:
            pay = PaymentRepo(db)
            total = pay.count_overdue(semester_id, faculty_id, class_id, major_id, before)
            info = page_info(total, page)
            info["rows"] = pay.list_overdue(semester_id, faculty_id, class_id, major_id, before,
                                            info["offset"], info["limit"])
            return info

    # ------------------------------------------------------------------ UC19
    def refund_or_adjust(self, actor, original_transaction_id, kind, amount, reason, basis, method="CASH",
                         approver="", confirmed=True, ip=None):
        """UC19 - BR-12: giao dich moi lien ket voi giao dich goc, khong sua/xoa giao dich cu."""
        require_role(actor, ROLE_FINANCE)
        if not confirmed:
            return None
        if kind not in ("REFUND", "ADJUSTMENT"):
            raise ServiceError("Choose Refund or Adjustment.")
        if (reason or "").strip() == "" or (basis or "").strip() == "":
            raise ServiceError("A reason and a basis are required.")
        amount = to_money(amount, "amount")
        if amount <= 0:
            raise ServiceError("The amount must be greater than 0.")
        full_reason = "%s | basis: %s" % (reason.strip(), basis.strip())
        if (approver or "").strip() != "":
            full_reason += " | approver: %s" % approver.strip()
        with self._db() as db:
            pay = PaymentRepo(db)
            original = pay.find_transaction(original_transaction_id)
            if original is None or original["transaction_type"] != "PAYMENT" or original["status"] != "CONFIRMED":
                raise ServiceError("No confirmed original payment transaction exists.")
            debt = pay.find_debt_by_id(original["debt_id"])
            if kind == "REFUND":
                refundable = original["amount"] - pay.sum_linked_refunds(original_transaction_id)
                if amount > refundable:
                    raise ServiceError("The refund exceeds the refundable amount (%s)." % refundable)
                status = "CONFIRMED" if method == "CASH" else "PENDING"  # hoan tien ngan hang chua xong -> PENDING
            else:
                method = method if method in ("CASH", "BANK_TRANSFER") else "CASH"
                status = "CONFIRMED"
            reference = "%s-%d-%d" % (kind[:3], original_transaction_id, int(time.time() * 1000) % 100000000)
            txn_id = pay.insert_transaction(reference, original["debt_id"], kind, amount, method, status,
                                            actor["account_id"], original_transaction_id, full_reason)
            AuditRepo(db).add(actor["account_id"], kind, "payment_transaction", str(txn_id), full_reason, ip)
            self.recalculate_debt(db, debt["student_id"], debt["semester_id"])
        return {"transaction_id": txn_id, "status": status}
