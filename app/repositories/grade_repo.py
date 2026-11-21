from datetime import datetime

from app.repositories.base_repo import BaseRepo


class GradeRepo(BaseRepo):
    """Bang grade (UC13, UC22, UC08)."""

    def find_grade(self, registration_id):
        return self.db.fetch_one("SELECT * FROM grade WHERE registration_id = %s", (registration_id,))

    def insert_grade(self, registration_id, process_score, exam_score, account_id):
        self.db.execute(
            "INSERT INTO grade (registration_id, process_score, exam_score, version, updated_at, updated_by) "
            "VALUES (%s, %s, %s, 0, %s, %s)",
            (registration_id, process_score, exam_score, datetime.now(), account_id))

    def update_grade(self, grade_id, process_score, exam_score, version, account_id):
        """NFR-PE-06: khoa lac quan - chi cap nhat neu version khong doi. Tra ve so dong da sua."""
        count, _ = self.db.execute(
            "UPDATE grade SET process_score = %s, exam_score = %s, version = version + 1, "
            "updated_at = %s, updated_by = %s WHERE grade_id = %s AND version = %s",
            (process_score, exam_score, datetime.now(), account_id, grade_id, version))
        return count

    def set_letter_grade(self, grade_id, letter_grade):
        self.db.execute("UPDATE grade SET letter_grade = %s WHERE grade_id = %s", (letter_grade, grade_id))

    def list_sheet(self, section_id):
        """UC22: bang diem cua cac sinh vien dang ky thanh cong (khong liet ke sinh vien da huy)."""
        return self.db.fetch_all(
            "SELECT r.registration_id, r.student_id, a.full_name, g.grade_id, g.process_score, g.exam_score, "
            "g.final_score, g.letter_grade, COALESCE(g.version, 0) AS version FROM course_registration r "
            "JOIN student s ON s.student_id = r.student_id JOIN account a ON a.account_id = s.account_id "
            "LEFT JOIN grade g ON g.registration_id = r.registration_id "
            "WHERE r.course_section_id = %s AND r.status = 'SUCCESSFUL' ORDER BY r.student_id", (section_id,))

    def list_incomplete(self, section_id):
        """UC08: sinh vien chua co diem tong ket."""
        return self.db.fetch_all(
            "SELECT r.student_id, a.full_name FROM course_registration r "
            "JOIN student s ON s.student_id = r.student_id JOIN account a ON a.account_id = s.account_id "
            "LEFT JOIN grade g ON g.registration_id = r.registration_id "
            "WHERE r.course_section_id = %s AND r.status = 'SUCCESSFUL' AND g.final_score IS NULL "
            "ORDER BY r.student_id", (section_id,))

    def count_registered_and_complete(self, section_id):
        row = self.db.fetch_one(
            "SELECT COUNT(*) AS registered, COALESCE(SUM(g.final_score IS NOT NULL), 0) AS complete "
            "FROM course_registration r LEFT JOIN grade g ON g.registration_id = r.registration_id "
            "WHERE r.course_section_id = %s AND r.status = 'SUCCESSFUL'", (section_id,))
        return int(row["registered"]), int(row["complete"])

    def list_published_for_student(self, student_id, semester_id):
        """BR-10 / NFR-SE-07: sinh vien chi thay diem cua lop co grade_status = PUBLISHED."""
        sql = ("SELECT cs.semester_id, s.subject_id, s.subject_name, s.credits, g.process_score, g.exam_score, "
               "g.final_score, g.letter_grade FROM course_registration r "
               "JOIN course_section cs ON cs.course_section_id = r.course_section_id "
               "JOIN subject s ON s.subject_id = cs.subject_id JOIN grade g ON g.registration_id = r.registration_id "
               "WHERE r.student_id = %s AND r.status = 'SUCCESSFUL' AND cs.grade_status = 'PUBLISHED'")
        params = [student_id]
        if semester_id:
            sql += " AND cs.semester_id = %s"
            params.append(semester_id)
        sql += " ORDER BY cs.semester_id, s.subject_id"
        return self.db.fetch_all(sql, tuple(params))

    def has_grade_entered(self, registration_id):
        row = self.db.fetch_one(
            "SELECT COUNT(*) AS total FROM grade WHERE registration_id = %s "
            "AND (process_score IS NOT NULL OR exam_score IS NOT NULL)", (registration_id,))
        return row["total"] > 0