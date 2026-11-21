import secrets
import string
from datetime import date, datetime

from app.config import Config


class ServiceError(Exception):
    """Loi nghiep vu: thong bao cho nguoi dung. errors = {ten_truong: thong_bao} de bao loi theo tung truong."""

    def __init__(self, message, errors=None):
        super().__init__(message)
        self.message = message
        self.errors = errors or {}


class PermissionDenied(ServiceError):
    pass


def require_role(user, *roles):
    """NFR-SE-02: kiem tra phan quyen o server truoc khi thuc hien thao tac."""
    if user is None:
        raise PermissionDenied("Please log in first.")
    for role in roles:
        if role in user["roles"]:
            return
    raise PermissionDenied("You do not have permission to perform this operation.")


def validation_error(errors):
    """Bao loi theo tung truong (UC05, UC07 ...)."""
    parts = []
    for field_name, message in errors.items():
        parts.append("%s: %s" % (field_name, message))
    return ServiceError("Please correct the following fields - " + "; ".join(parts), errors)


def generate_temp_password():
    """Mat khau tam thoi ngau nhien (UC04) - bat buoc doi o lan dang nhap dau."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(10))


def page_info(total, page):
    """NFR-US-05: phan trang, mac dinh 20 dong/trang."""
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    if page < 1:
        page = 1
    pages = (total + Config.PAGE_SIZE - 1) // Config.PAGE_SIZE
    if pages < 1:
        pages = 1
    return {"page": page, "pages": pages, "total": total, "offset": (page - 1) * Config.PAGE_SIZE,
            "limit": Config.PAGE_SIZE}


def parse_date(text, field_name):
    if isinstance(text, (date, datetime)):
        return text
    try:
        return datetime.strptime(str(text).strip(), "%Y-%m-%d").date()
    except ValueError:
        raise validation_error({field_name: "Invalid date (use YYYY-MM-DD)."})


def parse_datetime(text, field_name):
    if isinstance(text, datetime):
        return text
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(text).strip(), fmt)
        except ValueError:
            continue
    raise validation_error({field_name: "Invalid date/time (use YYYY-MM-DD HH:MM)."})