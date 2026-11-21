class BaseRepo:
    """Lop co so cua tang Data access: chi chua SQL, KHONG chua quy tac nghiep vu (SRS 2.9)."""

    def __init__(self, db):
        self.db = db