from datetime import date

from flask import Blueprint, render_template, request

from app.config import ROLE_FINANCE, ROLE_STUDENT, ROLE_TRAINING
from app.services.catalog_service import CatalogService
from app.services.fee_service import FeeService
from app.utils.export_handler import receipt_html
from app.web import empty_page, login_required, run_service, service_user

bp = Blueprint("fee", __name__)


@bp.route("/tuition", methods=["GET", "POST"])
@login_required(ROLE_FINANCE)
def tuition_setup():
    """UC14: don gia tin chi, chinh sach mien giam / hoc bong."""
    service = FeeService()
    actor = service_user()
    f = request.form
    if request.method == "POST":
        if f.get("action") == "rate":
            run_service(lambda: service.set_rate(
                actor, f.get("major_id"), f.get("semester_id"), f.get("academic_year"), f.get("price"),
                f.get("effective_from"), f.get("effective_to") or None, f.get("confirm_overlap") == "1"),
                "Tuition rate saved.")
        elif f.get("action") == "policy":
            run_service(lambda: service.create_policy(
                actor, f.get("policy_name"), f.get("policy_type"), f.get("value_type"), f.get("value"),
                f.get("conditions"), f.get("valid_from"), f.get("valid_to")), "Policy created.")
        elif f.get("action") == "assign":
            run_service(lambda: service.assign_waiver(
                actor, f.get("student_id"), int(f.get("policy_id") or 0), f.get("semester_id"), f.get("basis")),
                "Waiver assigned.")
    rates, _ = run_service(lambda: service.list_rates(actor), fallback=[])
    policies, _ = run_service(lambda: service.list_policies(actor), fallback=[])
    # Chi doc danh sach nganh / hoc ky cho o chon; CatalogService yeu cau vai tro TRAINING_MANAGER
    catalog, _ = run_service(lambda: CatalogService().list_all({"roles": [ROLE_TRAINING]}),
                             fallback={"majors": [], "semesters": []})
    return render_template("tuition_setup.html", rates=rates, policies=policies, catalog=catalog)


@bp.route("/collect", methods=["GET", "POST"])
@login_required(ROLE_FINANCE)
def collect_fee():
    """UC15: thu hoc phi; UC16: in bien lai."""
    service = FeeService()
    actor = service_user()
    f = request.form
    student_id = request.values.get("student_id", "").strip()
    if request.method == "POST":
        if f.get("action") == "pay":
            run_service(lambda: service.collect_payment(
                actor, student_id, f.get("semester_id"), f.get("amount"), f.get("method"), f.get("reference_code"),
                f.get("bank_verified") == "1", request.remote_addr), "Payment recorded.")
        elif f.get("action") == "confirm":
            run_service(lambda: service.confirm_transfer(actor, int(f.get("transaction_id")), request.remote_addr),
                        "Transfer confirmed.")
    info = None
    if student_id != "":
        info, _ = run_service(lambda: service.lookup_student(actor, student_id))
    return render_template("collect_fee.html", info=info, student_id=student_id)


@bp.route("/receipt/<int:transaction_id>")
@login_required(ROLE_FINANCE)
def receipt(transaction_id):
    data, failed = run_service(lambda: FeeService().print_receipt(service_user(), transaction_id))
    if failed:
        return "Receipt cannot be generated. Please go back and try again.", 400
    return receipt_html(data["transaction"], data["student"], data["is_copy"])


@bp.route("/debts", methods=["GET", "POST"])
@login_required(ROLE_FINANCE)
def debt_refund():
    """UC18: tra cuu cong no / no qua han; UC19: hoan tien / dieu chinh."""
    service = FeeService()
    actor = service_user()
    f = request.form
    if request.method == "POST" and f.get("action") == "refund":
        run_service(lambda: service.refund_or_adjust(
            actor, int(f.get("transaction_id") or 0), f.get("kind"), f.get("amount"), f.get("reason"),
            f.get("basis"), f.get("method") or "CASH", f.get("approver"), True, request.remote_addr),
            "Refund / adjustment recorded.")
    student_id = request.values.get("student_id", "").strip()
    info = None
    if student_id != "":
        info, _ = run_service(lambda: service.lookup_student(actor, student_id))
    a = request.args
    overdue, _ = run_service(
        lambda: service.overdue_list(actor, a.get("semester_id", ""), a.get("faculty_id", ""), a.get("class_id", ""),
                                     a.get("major_id", ""), a.get("overdue_before") or None, a.get("page", 1)),
        fallback=empty_page())
    return render_template("debt_refund.html", info=info, student_id=student_id, overdue=overdue,
                           today=date.today().isoformat())


@bp.route("/my-tuition")
@login_required(ROLE_STUDENT)
def my_tuition():
    """UC17: sinh vien xem cong no va lich su thanh toan cua chinh minh."""
    data, _ = run_service(lambda: FeeService().student_status(service_user()),
                          fallback={"debts": [], "transactions": []})
    return render_template("debt_refund.html", info=None, student_id="", overdue=None, mine=data,
                           today=date.today().isoformat
