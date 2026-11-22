from app.repositories.base_repo import BaseRepo


class EnrollRepo(BaseRepo):
    """Bang course_registration (UC10 - UC13, UC21)."""

    def find_registration(self, student_id, section_id):
        return self.db.fetch_one(
            "SELECT * FROM course_registration WHERE student_id = %s AND course_section_id = %s",
            (student_id, section_id))

    def find_registration_by_id(self, registration_id):
        return self.db.fetch_one(
            "SELECT * FROM course_registration WHERE registration_id = %s", (registration_id,))

    def insert_registration(self, student_id, section_id, registration_date):
        _, new_id = self.db.execute(
            "INSERT INTO course_registration (student_id, course_section_id, registration_date, status) "
            "VALUES (%s, %s, %s, 'SUCCESSFUL')", (student_id, section_id, registration_date))
        return new_id

    def reactivate(self, registration_id, registration_date):
        # Dang ky lai lop da huy: cap nhat chinh dong cu (SRS 6.2.15)
        self.db.execute(
            "UPDATE course_registration SET status = 'SUCCESSFUL', registration_date = %s, cancelled_at = NULL "
            "WHERE registration_id = %s", (registration_date, registration_id))

    def cancel(self, registration_id, cancelled_at):
        self.db.execute(
            "UPDATE course_registration SET status = 'CANCELLED', cancelled_at = %s WHERE registration_id = %s",
            (cancelled_at, registration_id))

    def count_successful(self, section_id):
        row = self.db.fetch_one(
            "SELECT COUNT(*) AS total FROM course_registration WHERE course_section_id = %s "
            "AND status = 'SUCCESSFUL'", (section_id,))
        return row["total"]

    def sum_credits(self, student_id, semester_id):
        row = self.db.fetch_one(
            "SELECT COALESCE(SUM(s.credits), 0) AS total FROM course_registration r "
            "JOIN course_section cs ON cs.course_section_id = r.course_section_id "
            "JOIN subject s ON s.subject_id = cs.subject_id "
            "WHERE r.student_id = %s AND cs.semester_id = %s AND r.status = 'SUCCESSFUL'",
            (student_id, semester_id))
        return int(row["total"])

    def list_student_sections(self, student_id, semester_id):
        """Cac lop hoc phan dang ky thanh cong cua sinh vien trong hoc ky (thoi khoa bieu)."""
        return self.db.fetch_all(
            "SELECT r.registration_id, r.status, r.registration_date, cs.course_section_id, cs.day_of_week, "
            "cs.start_period, cs.period_count, cs.classroom, cs.semester_id, s.subject_id, s.subject_name, "
            "s.credits, a.full_name AS lecturer_name FROM course_registration r "
            "JOIN course_section cs ON cs.course_section_id = r.course_section_id "
            "JOIN subject s ON s.subject_id = cs.subject_id "
            "LEFT JOIN lecturer l ON l.lecturer_id = cs.lecturer_id "
            "LEFT JOIN account a ON a.account_id = l.account_id "
            "WHERE r.student_id = %s AND cs.semester_id = %s AND r.status = 'SUCCESSFUL' "
            "ORDER BY cs.day_of_week, cs.start_period", (student_id, semester_id))

    def has_passed(self, student_id, subject_id, pass_threshold):
        """BR-07: da dat mon hoc (diem tong ket >= nguong, bang diem da khoa hoac cong bo)."""
        row = self.db.fetch_one(
            "SELECT COUNT(*) AS total FROM course_registration r "
            "JOIN course_section cs ON cs.course_section_id = r.course_section_id "
            "JOIN grade g ON g.registration_id = r.registration_id "
            "WHERE r.student_id = %s AND cs.subject_id = %s AND r.status = 'SUCCESSFUL' "
            "AND cs.grade_status IN ('LOCKED', 'PUBLISHED') AND g.final_score >= %s",
            (student_id, subject_id, pass_threshold))
        return row["total"] > 0

    def list_class(self, section_id, offset, limit):
        """UC21: chi sinh vien co trang thai SUCCESSFUL."""
        return self.db.fetch_all(
            "SELECT s.student_id, a.full_name, s.class_id, a.email FROM course_registration r "
            "JOIN student s ON s.student_id = r.student_id JOIN account a ON a.account_id = s.account_id "
            "WHERE r.course_section_id = %s AND r.status = 'SUCCESSFUL' ORDER BY s.student_id LIMIT %s OFFSET %s",
            (section_id, limit, offset))

    def find_student_major(self, student_id):
        row = self.db.fetch_one(
            "SELECT c.major_id FROM student s JOIN administrative_class c ON c.class_id = s.class_id "
            "WHERE s.student_id = %s", (student_id,))
        if row is None:
            return None
        return row["major_id"]
