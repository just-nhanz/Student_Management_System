"""Cap nhat mat khau mau cho cac tai khoan trong seed.sql.
Chay: python -m app.utils.seed_passwords
"""
from app.utils.database import Database
from app.utils.security import hash_password


def main():
    with Database() as db:
        admin_hash = hash_password("Admin@123")
        student_hash = hash_password("123456")
        for username in ("admin", "training", "finance", "lecturer01"):
            db.execute("UPDATE account SET password_hash = %s WHERE username = %s", (admin_hash, username))
        db.execute("UPDATE account SET password_hash = %s WHERE username = %s", (student_hash, "student01"))
    print("Da cap nhat mat khau mau.")


if __name__ == "__main__":
    main()