import re

import bcrypt

from app.config import Config


def hash_password(plain):
    """NFR-SE-03: bcrypt co salt, cost >= 12. Khong bao gio luu/ghi log mat khau goc."""
    salt = bcrypt.gensalt(rounds=Config.BCRYPT_ROUNDS)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain, password_hash):
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def check_password_policy(password):
    """UC03: tra ve thong bao loi neu mat khau khong dat chinh sach, nguoc lai tra ve None."""
    if len(password) < Config.PASSWORD_MIN_LENGTH:
        return "Password must be at least %d characters." % Config.PASSWORD_MIN_LENGTH
    return None


def is_valid_email(email):
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email or "") is not None


def is_valid_phone(phone):
    # Dien thoai tuy chon; neu co thi 8-15 chu so (UC05)
    if phone is None or phone == "":
        return True
    return re.match(r"^\+?[0-9]{8,15}$", phone) is not None