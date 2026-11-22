from flask import Blueprint, redirect, render_template, request, session, url_for

from app.config import ROLE_ADMIN, ROLE_FINANCE, ROLE_LECTURER, ROLE_STUDENT, ROLE_TRAINING
from app.services.auth_service import AuthService
from app.web import current_user, login_required, run_service, service_user

bp = Blueprint("login", __name__)

HOME = {
    ROLE_ADMIN: "login.accounts",
    ROLE_TRAINING: "student.students",
    ROLE_FINANCE: "fee.tuition_setup",
    ROLE_LECTURER: "grade.teaching_schedule",
    ROLE_STUDENT: "enroll.course_register",
}


@bp.route("/", methods=["GET"])
def index():
    user = current_user()
    if user is None:
        return redirect(url_for("login.login"))
    return redirect(url_for(HOME[user["active_role"]]))


@bp.route("/login", methods=["GET", "POST"])
def login():
    """UC01: dang nhap."""
    if request.method == "POST":
        result, failed = run_service(
            lambda: AuthService().login(request.form.get("username"), request.form.get("password"),
                                        request.remote_addr))
        if not failed:
            csrf = session.get("csrf_token")
            session.clear()                      # NFR-SE-01: doi session sau khi dang nhap
            session["csrf_token"] = csrf
            session["user"] = result
            return redirect(url_for("login.index"))
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
@login_required()
def logout():
    """UC02: dang xuat (form co buoc xac nhan o giao dien)."""
    session.clear()
    return redirect(url_for("login.login"))


@bp.route("/switch-role", methods=["POST"])
@login_required()
def switch_role():
    """Nguoi dung nhieu vai tro chon vai tro dang dung (SRS muc 7)."""
    role = request.form.get("role")
    user = session["user"]
    if role in user["roles"]:
        user["active_role"] = role
        session["user"] = user
    return redirect(url_for("login.index"))


@bp.route("/change-password", methods=["GET", "POST"])
@login_required()
def change_password():
    """UC03: doi mat khau."""
    if request.method == "POST":
        _, failed = run_service(
            lambda: AuthService().change_password(
                service_user(), request.form.get("current_password"), request.form.get("new_password"),
                request.form.get("confirm_password")),
            "Password changed successfully.")
        if not failed:
            user = session["user"]
            user["must_change_password"] = False
            session["user"] = user
            return redirect(url_for("login.index"))
    return render_template("login.html", change_password=True)


@bp.route("/accounts", methods=["GET", "POST"])
@login_required(ROLE_ADMIN)
def accounts():
    """UC04: quan ly tai khoan."""
    service = AuthService()
    created = None
    if request.method == "POST":
        action = request.form.get("action")
        admin = service_user()
        ip = request.remote_addr
        if action == "create":
            created, _ = run_service(lambda: service.create_account(
                admin, request.form.get("username"), request.form.get("full_name"), request.form.get("email"),
                request.form.get("phone_number"), request.form.getlist("roles"), ip), "Account created.")
        elif action == "lock":
            run_service(lambda: service.lock_account(admin, int(request.form["account_id"]),
                                                     request.form.get("reason"), True, ip), "Account locked.")
        elif action == "unlock":
            run_service(lambda: service.unlock_account(admin, int(request.form["account_id"]),
                                                       request.form.get("reason"), True, ip), "Account unlocked.")
        elif action == "reset":
            created, _ = run_service(lambda: {"temporary_password": service.reset_password(
                admin, int(request.form["account_id"]), True, ip)}, "Password reset.")
        elif action == "roles":
            run_service(lambda: service.assign_roles(admin, int(request.form["account_id"]),
                                                     request.form.getlist("roles"), ip), "Roles updated.")
    rows, _ = run_service(lambda: service.list_accounts(service_user()), fallback=[])
    return render_template("account_admin.html", accounts=rows, created=created,
                           role_names=["SYSTEM_ADMIN", "TRAINING_MANAGER", "FINANCE_MANAGER", "LECTURER", "STUDENT"])
