from app.repositories.base_repo import BaseRepo


class UserRepo(BaseRepo):
    """Bang student, lecturer (ho so) - UC05, UC06."""

    # ---------- student ----------
    def find_student(self, student_id):
        return self.db.fetch_one(
            "SELECT s.*, a.full_name, a.email, a.phone_number, a.username FROM student s "
            "JOIN account a ON a.account_id = s.account_id WHERE s.student_id = %s", (student_id,))

    def find_student_by_account(self, account_id):
        return self.db.fetch_one(
            "SELECT s.*, a.full_name, a.email, a.phone_number FROM student s "
            "JOIN account a ON a.account_id = s.account_id WHERE s.account_id = %s", (account_id,))

    def insert_student(self, student_id, account_id, class_id, date_of_birth, gender, address):
        self.db.execute(
            "INSERT INTO student (student_id, account_id, class_id, date_of_birth, gender, address, "
            "academic_status, record_status) VALUES (%s, %s, %s, %s, %s, %s, 'STUDYING', 'ACTIVE')",
            (student_id, account_id, class_id, date_of_birth, gender, address))

    def update_student(self, student_id, class_id, date_of_birth, gender, address, academic_status):
        self.db.execute(
            "UPDATE student SET class_id = %s, date_of_birth = %s, gender = %s, address = %s, "
            "academic_status = %s WHERE student_id = %s",
            (class_id, date_of_birth, gender, address, academic_status, student_id))

    def set_student_record_status(self, student_id, record_status):
        self.db.execute("UPDATE student SET record_status = %s WHERE student_id = %s", (record_status, student_id))

    def search_students(self, keyword, class_id, offset, limit):
        sql = ("SELECT s.student_id, a.full_name, a.email, a.phone_number, s.class_id, s.academic_status, "
               "s.record_status FROM student s JOIN account a ON a.account_id = s.account_id WHERE 1 = 1")
        params = []
        if keyword:
            sql += " AND (s.student_id LIKE %s OR a.full_name LIKE %s)"
            params.append("%" + keyword + "%")
            params.append("%" + keyword + "%")
        if class_id:
            sql += " AND s.class_id = %s"
            params.append(class_id)
        sql += " ORDER BY s.student_id LIMIT %s OFFSET %s"
        params.append(limit)
        params.append(offset)
        return self.db.fetch_all(sql, tuple(params))

    def count_students(self, keyword, class_id):
        sql = ("SELECT COUNT(*) AS total FROM student s JOIN account a ON a.account_id = s.account_id "
               "WHERE 1 = 1")
        params = []
        if keyword:
            sql += " AND (s.student_id LIKE %s OR a.full_name LIKE %s)"
            params.append("%" + keyword + "%")
            params.append("%" + keyword + "%")
        if class_id:
            sql += " AND s.class_id = %s"
            params.append(class_id)
        return self.db.fetch_one(sql, tuple(params))["total"]

    def student_has_history(self, student_id):
        """BR-02: sinh vien da co dang ky / hoc phi / diem thi khong duoc xoa vat ly."""
        row = self.db.fetch_one(
            "SELECT (SELECT COUNT(*) FROM course_registration WHERE student_id = %s) + "
            "(SELECT COUNT(*) FROM student_debt WHERE student_id = %s) AS total", (student_id, student_id))
        return row["total"] > 0

    # ---------- lecturer ----------
    def find_lecturer(self, lecturer_id):
        return self.db.fetch_one(
            "SELECT l.*, a.full_name, a.email, a.phone_number FROM lecturer l "
            "JOIN account a ON a.account_id = l.account_id WHERE l.lecturer_id = %s", (lecturer_id,))

    def find_lecturer_by_account(self, account_id):
        return self.db.fetch_one(
            "SELECT l.*, a.full_name, a.email, a.phone_number FROM lecturer l "
            "JOIN account a ON a.account_id = l.account_id WHERE l.account_id = %s", (account_id,))

    def insert_lecturer(self, lecturer_id, account_id, faculty_id, degree, specialization):
        self.db.execute(
            "INSERT INTO lecturer (lecturer_id, account_id, faculty_id, degree, specialization, employment_status) "
            "VALUES (%s, %s, %s, %s, %s, 'ACTIVE')",
            (lecturer_id, account_id, faculty_id, degree, specialization))

    def update_lecturer(self, lecturer_id, faculty_id, degree, specialization):
        self.db.execute(
            "UPDATE lecturer SET faculty_id = %s, degree = %s, specialization = %s WHERE lecturer_id = %s",
            (faculty_id, degree, specialization, lecturer_id))

    def set_lecturer_status(self, lecturer_id, employment_status):
        self.db.execute(
            "UPDATE lecturer SET employment_status = %s WHERE lecturer_id = %s", (employment_status, lecturer_id))

    def search_lecturers(self, keyword, offset, limit):
        sql = ("SELECT l.lecturer_id, a.full_name, a.email, a.phone_number, l.faculty_id, l.degree, "
               "l.specialization, l.employment_status FROM lecturer l JOIN account a ON a.account_id = l.account_id "
               "WHERE 1 = 1")
        params = []
        if keyword:
            sql += " AND (l.lecturer_id LIKE %s OR a.full_name LIKE %s OR a.email LIKE %s OR a.phone_number LIKE %s)"
            for _ in range(4):
                params.append("%" + keyword + "%")
        sql += " ORDER BY l.lecturer_id LIMIT %s OFFSET %s"
        params.append(limit)
        params.append(offset)
        return self.db.fetch_all(sql, tuple(params))

    def count_lecturers(self, keyword):
        sql = ("SELECT COUNT(*) AS total FROM lecturer l JOIN account a ON a.account_id = l.account_id "
               "WHERE 1 = 1")
        params = []
        if keyword:
            sql += " AND (l.lecturer_id LIKE %s OR a.full_name LIKE %s OR a.email LIKE %s OR a.phone_number LIKE %s)"
            for _ in range(4):
                params.append("%" + keyword + "%")
        return self.db.fetch_one(sql, tuple(params))["total"]

    def lecturer_has_sections(self, lecturer_id):
        """UC06: giang vien dang duoc phan cong thi khong cho khoa."""
        row = self.db.fetch_one(
            "SELECT COUNT(*) AS total FROM course_section WHERE lecturer_id = %s", (lecturer_id,))
        return row["total"] > 0
        
