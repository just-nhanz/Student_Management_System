import secrets
from datetime import timedelta
from functools import wraps

from flask import Flask, abort, flash, g, redirect, request, session, url_for

from app.config import Config
from app.services import PermissionDenied, ServiceError


def current_user():
    return session.get("user")


def login_required(*roles):
    """NFR-SE-02: kiem tra dang nhap + vai tro dang chon (active_role) tren server."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return redirect(url_for("login.login"))
            if user.get("must_change_password") and request.endpoint not in ("login.change_password", "login.logout"):
                return redirect(url_for("login.change_password"))
            if len(roles) > 0 and user.get("active_role") not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapper
    return decorator


def service_user():
    """Dang user cho service: chi giu vai tro dang chon de service kiem tra quyen."""
    user = dict(session["user"])
    user["roles"] = [user["active_role"]]
    return user


def run_service(action, success_message=None, fallback=None):
    """Chay mot thao tac service; loi nghiep vu duoc flash ra (NFR-US-03). Tra ve (ket_qua, co_loi)."""
    try:
        result = action()
        if success_message:
            flash(success_message, "success")
        return result, False
    except PermissionDenied as error:
        flash(error.message, "error")
        return fallback, True
    except ServiceError as error:
        flash(error.message, "error")
        return fallback, True


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = Config.SECRET_KEY
    # NFR-SE-01: cookie HttpOnly, SameSite=Lax, het han sau 30 phut khong hoat dong
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = False   # dat True khi chay sau HTTPS
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=Config.SESSION_TIMEOUT_MINUTES)
    app.config["MAX_CONTENT_LENGTH"] = Config.IMPORT_MAX_FILE_MB * 1024 * 1024

    @app.before_request
    def protect():
        # NFR-SE-04: CSRF token cho moi form thay doi trang thai
        session.permanent = True
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(16)
        if request.method == "POST":
            if request.form.get("csrf_token") != session.get("csrf_token"):
                abort(400)

    @app.context_processor
    def inject():
        return {"csrf_token": session.get("csrf_token", ""), "user": current_user()}

    @app.errorhandler(403)
    def forbidden(_):
        return "403 - You do not have permission to open this page.", 403

    @app.errorhandler(Exception)
    def failure(error):
        # NFR-RE-03: khong lo chi tiet noi bo cho nguoi dung
        from werkzeug.exceptions import HTTPException
        if isinstance(error, HTTPException):
            return error
        app.logger.exception("Unhandled error")
        return "A system error occurred. Please try again later.", 500

    from app.web.routes.login_routes import bp as login_bp
    from app.web.routes.student_routes import bp as student_bp
    from app.web.routes.catalog_routes import bp as catalog_bp
    from app.web.routes.enroll_routes import bp as enroll_bp
    from app.web.routes.fee_routes import bp as fee_bp
    from app.web.routes.grade_routes import bp as grade_bp
    for blueprint in (login_bp, student_bp, catalog_bp, enroll_bp, fee_bp, grade_bp):
        app.register_blueprint(blueprint)
    return app