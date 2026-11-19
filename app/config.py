import os


class Config:
    # Ket noi MySQL 8.0 (NFR-TS-02) - cau hinh nam ngoai code (NFR - Maintainability)
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "sms_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "sms_pass")
    DB_NAME = os.getenv("DB_NAME", "sms")

    SECRET_KEY = os.getenv("SECRET_KEY", "doi-khoa-bi-mat-nay")

    # NFR-SE-03: bcrypt cost >= 12 (test co the ha xuong de chay nhanh)
    BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))

    # BR-01 / UC01 / NFR-SE-06: khoa tai khoan sau 5 lan sai
    MAX_FAILED_ATTEMPTS = int(os.getenv("MAX_FAILED_ATTEMPTS", "5"))
    # NFR-SE-01: het han phien sau 30 phut khong hoat dong
    SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))
    # Chinh sach mat khau (UC03): do dai toi thieu (mat khau mau "123456" hop le)
    PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "6"))

    # SRS 1.6: ngưỡng cấu hình bởi nhà trường
    PASS_THRESHOLD = float(os.getenv("PASS_THRESHOLD", "4.0"))          # BR-07
    PROCESS_WEIGHT = float(os.getenv("PROCESS_WEIGHT", "0.4"))          # UC22.3 (khop cot final_score)
    EXAM_WEIGHT = float(os.getenv("EXAM_WEIGHT", "0.6"))
    DEBT_THRESHOLD = float(os.getenv("DEBT_THRESHOLD", "0"))            # BR-08: no qua han > nguong thi chan dang ky
    DEFAULT_MAX_CREDITS = int(os.getenv("DEFAULT_MAX_CREDITS", "24"))

    # NFR-US-05: moi trang 20 dong
    PAGE_SIZE = int(os.getenv("PAGE_SIZE", "20"))

    # UC05: gioi han file import (cau hinh duoc)
    IMPORT_MAX_FILE_MB = int(os.getenv("IMPORT_MAX_FILE_MB", "5"))
    IMPORT_MAX_ROWS = int(os.getenv("IMPORT_MAX_ROWS", "1000"))

    # NFR-US-02 / UC22: bang quy doi diem chu (diem toi thieu, chu cai)
    LETTER_SCALE = [(8.5, "A"), (7.0, "B"), (5.5, "C"), (4.0, "D"), (0.0, "F")]


# Ten vai tro (SRS 6.2.2)
ROLE_ADMIN = "SYSTEM_ADMIN"
ROLE_TRAINING = "TRAINING_MANAGER"
ROLE_FINANCE = "FINANCE_MANAGER"
ROLE_LECTURER = "LECTURER"
ROLE_STUDENT = "STUDENT"