import pymysql
from pymysql.cursors import DictCursor

from app.config import Config


def get_connection():
    """Mo ket noi MySQL moi. autocommit tat de service dieu khien transaction (NFR-RE-02)."""
    return pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )


class Database:
    """Boc ket noi + transaction. Dung: with Database() as db: repo = XRepo(db)."""

    def __init__(self, connection=None):
        self._external = connection is not None
        self.conn = connection if connection is not None else get_connection()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        # NFR-RE-03: loi -> rollback, khong de du lieu hong
        if exc_type is not None:
            self.conn.rollback()
        else:
            self.conn.commit()
        if not self._external:
            self.conn.close()
        return False

    def execute(self, sql, params=()):
        """INSERT/UPDATE/DELETE - tra ve so dong va lastrowid."""
        cur = self.conn.cursor()
        cur.execute(sql, params)
        last_id = cur.lastrowid
        count = cur.rowcount
        cur.close()
        return count, last_id

    def fetch_one(self, sql, params=()):
        cur = self.conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        cur.close()
        return row

    def fetch_all(self, sql, params=()):
        cur = self.conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return rows