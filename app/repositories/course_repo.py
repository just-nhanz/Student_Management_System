from app.repositories.base_repo import BaseRepo

ENROLLED_SQL = ("(SELECT COUNT(*) FROM course_registration r WHERE r.course_section_id = cs.course_section_id "
                "AND r.status = 'SUCCESSFUL') AS enrolled")


class CourseRepo(BaseRepo):
    """Bang course_section (UC08, UC09, UC20)."""

    def find_section(self, section_id):
        return self.db.fetch_one(
            "SELECT cs.*, s.subject_name, s.credits, s.status AS subject_status, " + ENROLLED_SQL + " "
            "FROM course_section cs JOIN subject s ON s.subject_id = cs.subject_id "
            "WHERE cs.course_section_id = %s", (section_id,))

    def find_section_for_update(self, section_id):
        # NFR-PE-04: khoa dong de cac yeu cau dang ky dong thoi phai cho nhau
        return self.db.fetch_one(
            "SELECT * FROM course_section WHERE course_section_id = %s FOR UPDATE", (section_id,))

    def next_section_no(self, subject_id, semester_id):
        row = self.db.fetch_one(
            "SELECT COALESCE(MAX(section_no), 0) + 1 AS next_no FROM course_section "
            "WHERE subject_id = %s AND semester_id = %s", (subject_id, semester_id))
        return row["next_no"]

    def insert_section(self, section_id, subject_id, semester_id, section_no, classroom, day_of_week,
                       start_period, period_count, max_capacity):
        self.db.execute(
            "INSERT INTO course_section (course_section_id, subject_id, semester_id, section_no, classroom, "
            "day_of_week, start_period, period_count, max_capacity, status, grade_status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'OPEN', 'UNLOCKED')",
            (section_id, subject_id, semester_id, section_no, classroom, day_of_week, start_period,
             period_count, max_capacity))

    def list_sections(self, semester_id):
        return self.db.fetch_all(
            "SELECT cs.*, s.subject_name, s.credits, a.full_name AS lecturer_name, " + ENROLLED_SQL + " "
            "FROM course_section cs JOIN subject s ON s.subject_id = cs.subject_id "
            "LEFT JOIN lecturer l ON l.lecturer_id = cs.lecturer_id "
            "LEFT JOIN account a ON a.account_id = l.account_id "
            "WHERE cs.semester_id = %s ORDER BY cs.course_section_id", (semester_id,))

    def list_open_sections(self, semester_id):
        return self.db.fetch_all(
            "SELECT cs.*, s.subject_name, s.credits, a.full_name AS lecturer_name, " + ENROLLED_SQL + " "
            "FROM course_section cs JOIN subject s ON s.subject_id = cs.subject_id "
            "LEFT JOIN lecturer l ON l.lecturer_id = cs.lecturer_id "
            "LEFT JOIN account a ON a.account_id = l.account_id "
            "WHERE cs.semester_id = %s AND cs.status = 'OPEN' ORDER BY cs.course_section_id", (semester_id,))

    def find_room_conflict(self, semester_id, classroom, day_of_week, start_period, end_period):
        """Tim lop hoc phan cung phong, cung ngay, trung tiet."""
        return self.db.fetch_one(
            "SELECT course_section_id FROM course_section WHERE semester_id = %s AND classroom = %s "
            "AND day_of_week = %s AND start_period <= %s AND (start_period + period_count - 1) >= %s LIMIT 1",
            (semester_id, classroom, day_of_week, end_period, start_period))

    def find_lecturer_conflict(self, lecturer_id, semester_id, day_of_week, start_period, end_period, exclude_id):
        return self.db.fetch_one(
            "SELECT course_section_id FROM course_section WHERE lecturer_id = %s AND semester_id = %s "
            "AND day_of_week = %s AND start_period <= %s AND (start_period + period_count - 1) >= %s "
            "AND course_section_id <> %s LIMIT 1",
            (lecturer_id, semester_id, day_of_week, end_period, start_period, exclude_id))

    def set_lecturer(self, section_id, lecturer_id):
        self.db.execute(
            "UPDATE course_section SET lecturer_id = %s WHERE course_section_id = %s", (lecturer_id, section_id))

    def set_grade_status(self, section_id, grade_status):
        self.db.execute(
            "UPDATE course_section SET grade_status = %s WHERE course_section_id = %s", (grade_status, section_id))

    def list_by_lecturer(self, lecturer_id, semester_id):
        return self.db.fetch_all(
            "SELECT cs.*, s.subject_name, s.credits, " + ENROLLED_SQL + " FROM course_section cs "
            "JOIN subject s ON s.subject_id = cs.subject_id "
            "WHERE cs.lecturer_id = %s AND cs.semester_id = %s ORDER BY cs.day_of_week, cs.start_period",
            (lecturer_id, semester_id))