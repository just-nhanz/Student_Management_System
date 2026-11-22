from app.repositories.base_repo import BaseRepo


class CatalogRepo(BaseRepo):
    """Bang faculty, major, administrative_class, subject, subject_prerequisite, curriculum_subject, semester (UC07)."""

    # ---------- faculty ----------
    def find_faculty(self, faculty_id):
        return self.db.fetch_one("SELECT * FROM faculty WHERE faculty_id = %s", (faculty_id,))

    def find_faculty_by_name(self, name):
        return self.db.fetch_one("SELECT * FROM faculty WHERE faculty_name = %s", (name,))

    def list_faculties(self):
        return self.db.fetch_all("SELECT * FROM faculty ORDER BY faculty_id")

    def insert_faculty(self, faculty_id, faculty_name, description):
        self.db.execute(
            "INSERT INTO faculty (faculty_id, faculty_name, description, status) VALUES (%s, %s, %s, 'ACTIVE')",
            (faculty_id, faculty_name, description))

    def update_faculty(self, faculty_id, faculty_name, description):
        self.db.execute(
            "UPDATE faculty SET faculty_name = %s, description = %s WHERE faculty_id = %s",
            (faculty_name, description, faculty_id))

    def set_faculty_status(self, faculty_id, status):
        self.db.execute("UPDATE faculty SET status = %s WHERE faculty_id = %s", (status, faculty_id))

    def faculty_dependents(self, faculty_id):
        row = self.db.fetch_one(
            "SELECT (SELECT COUNT(*) FROM major WHERE faculty_id = %s AND status = 'ACTIVE') + "
            "(SELECT COUNT(*) FROM lecturer WHERE faculty_id = %s AND employment_status = 'ACTIVE') + "
            "(SELECT COUNT(*) FROM subject WHERE faculty_id = %s AND status = 'ACTIVE') AS total",
            (faculty_id, faculty_id, faculty_id))
        return row["total"]

    # ---------- major ----------
    def find_major(self, major_id):
        return self.db.fetch_one("SELECT * FROM major WHERE major_id = %s", (major_id,))

    def list_majors(self):
        return self.db.fetch_all("SELECT * FROM major ORDER BY major_id")

    def insert_major(self, major_id, major_name, faculty_id):
        self.db.execute(
            "INSERT INTO major (major_id, major_name, faculty_id, status) VALUES (%s, %s, %s, 'ACTIVE')",
            (major_id, major_name, faculty_id))

    def update_major(self, major_id, major_name, faculty_id):
        self.db.execute(
            "UPDATE major SET major_name = %s, faculty_id = %s WHERE major_id = %s",
            (major_name, faculty_id, major_id))

    def set_major_status(self, major_id, status):
        self.db.execute("UPDATE major SET status = %s WHERE major_id = %s", (status, major_id))

    def major_dependents(self, major_id):
        row = self.db.fetch_one(
            "SELECT COUNT(*) AS total FROM administrative_class WHERE major_id = %s AND status = 'ACTIVE'",
            (major_id,))
        return row["total"]

    # ---------- administrative class ----------
    def find_class(self, class_id):
        return self.db.fetch_one("SELECT * FROM administrative_class WHERE class_id = %s", (class_id,))

    def list_classes(self):
        return self.db.fetch_all("SELECT * FROM administrative_class ORDER BY class_id")

    def insert_class(self, class_id, class_name, major_id, academic_year):
        self.db.execute(
            "INSERT INTO administrative_class (class_id, class_name, major_id, academic_year, status) "
            "VALUES (%s, %s, %s, %s, 'ACTIVE')", (class_id, class_name, major_id, academic_year))

    def update_class(self, class_id, class_name, major_id, academic_year):
        self.db.execute(
            "UPDATE administrative_class SET class_name = %s, major_id = %s, academic_year = %s WHERE class_id = %s",
            (class_name, major_id, academic_year, class_id))

    def set_class_status(self, class_id, status):
        self.db.execute("UPDATE administrative_class SET status = %s WHERE class_id = %s", (status, class_id))

    def class_dependents(self, class_id):
        row = self.db.fetch_one("SELECT COUNT(*) AS total FROM student WHERE class_id = %s", (class_id,))
        return row["total"]

    # ---------- subject ----------
    def find_subject(self, subject_id):
        return self.db.fetch_one("SELECT * FROM subject WHERE subject_id = %s", (subject_id,))

    def list_subjects(self):
        return self.db.fetch_all("SELECT * FROM subject ORDER BY subject_id")

    def insert_subject(self, subject_id, subject_name, credits, faculty_id):
        self.db.execute(
            "INSERT INTO subject (subject_id, subject_name, credits, faculty_id, status) "
            "VALUES (%s, %s, %s, %s, 'ACTIVE')", (subject_id, subject_name, credits, faculty_id))

    def update_subject(self, subject_id, subject_name, credits, faculty_id):
        self.db.execute(
            "UPDATE subject SET subject_name = %s, credits = %s, faculty_id = %s WHERE subject_id = %s",
            (subject_name, credits, faculty_id, subject_id))

    def set_subject_status(self, subject_id, status):
        self.db.execute("UPDATE subject SET status = %s WHERE subject_id = %s", (status, subject_id))

    def subject_used_in_sections(self, subject_id):
        row = self.db.fetch_one(
            "SELECT COUNT(*) AS total FROM course_section WHERE subject_id = %s", (subject_id,))
        return row["total"] > 0

    # ---------- prerequisite ----------
    def list_prerequisites(self, subject_id):
        rows = self.db.fetch_all(
            "SELECT prerequisite_id FROM subject_prerequisite WHERE subject_id = %s", (subject_id,))
        result = []
        for row in rows:
            result.append(row["prerequisite_id"])
        return result

    def add_prerequisite(self, subject_id, prerequisite_id):
        self.db.execute(
            "INSERT IGNORE INTO subject_prerequisite (subject_id, prerequisite_id) VALUES (%s, %s)",
            (subject_id, prerequisite_id))

    def remove_prerequisite(self, subject_id, prerequisite_id):
        self.db.execute(
            "DELETE FROM subject_prerequisite WHERE subject_id = %s AND prerequisite_id = %s",
            (subject_id, prerequisite_id))

    # ---------- curriculum ----------
    def set_curriculum(self, major_id, subject_id, is_required, recommended_semester):
        self.db.execute(
            "INSERT INTO curriculum_subject (major_id, subject_id, is_required, recommended_semester) "
            "VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE is_required = VALUES(is_required), "
            "recommended_semester = VALUES(recommended_semester)",
            (major_id, subject_id, is_required, recommended_semester))

    def list_curriculum(self, major_id):
        return self.db.fetch_all(
            "SELECT c.*, s.subject_name, s.credits FROM curriculum_subject c "
            "JOIN subject s ON s.subject_id = c.subject_id WHERE c.major_id = %s "
            "ORDER BY c.recommended_semester, c.subject_id", (major_id,))

    # ---------- semester ----------
    def find_semester(self, semester_id):
        return self.db.fetch_one("SELECT * FROM semester WHERE semester_id = %s", (semester_id,))

    def list_semesters(self):
        return self.db.fetch_all("SELECT * FROM semester ORDER BY start_date DESC")

    def insert_semester(self, semester_id, semester_name, start_date, end_date, reg_start, reg_end,
                        cancel_deadline, max_credits):
        self.db.execute(
            "INSERT INTO semester (semester_id, semester_name, start_date, end_date, reg_start, reg_end, "
            "cancel_deadline, max_credits) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (semester_id, semester_name, start_date, end_date, reg_start, reg_end, cancel_deadline, max_credits))

    def update_semester(self, semester_id, semester_name, start_date, end_date, reg_start, reg_end,
                        cancel_deadline, max_credits):
        self.db.execute(
            "UPDATE semester SET semester_name = %s, start_date = %s, end_date = %s, reg_start = %s, "
            "reg_end = %s, cancel_deadline = %s, max_credits = %s WHERE semester_id = %s",
            (semester_name, start_date, end_date, reg_start, reg_end, cancel_deadline, max_credits, semester_id))

    def semester_dependents(self, semester_id):
        row = self.db.fetch_one(
            "SELECT COUNT(*) AS total FROM course_section WHERE semester_id = %s", (semester_id,))
        return row["total"]