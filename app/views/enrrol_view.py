from tkinter import messagebox, ttk

from app.gui.components.widgets import DataTable, FormFields, acting_user, confirm, open_html, run
from app.services.catalog_service import CatalogService
from app.services.enroll_service import EnrollService
from app.utils.export_handler import timetable_html, transcript_html


class SectionAdminView(ttk.Frame):
    """UC08 (mo lop hoc phan) va UC09 (phan cong giang vien)."""

    def __init__(self, parent, user):
        super().__init__(parent, padding=10)
        self.user = acting_user(user)
        self.service = EnrollService()
        catalog, failed = run(lambda: CatalogService().list_all(self.user))
        if failed:
            catalog = {"subjects": [], "semesters": []}
        subject_ids = []
        for row in catalog["subjects"]:
            if row["status"] == "ACTIVE":
                subject_ids.append(row["subject_id"])
        semester_ids = [row["semester_id"] for row in catalog["semesters"]]

        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Semester").pack(side="left")
        self.semester_filter = ttk.Combobox(top, values=semester_ids, width=12, state="readonly")
        self.semester_filter.pack(side="left", padx=4)
        ttk.Button(top, text="Show", command=self.refresh).pack(side="left")

        self.table = DataTable(self, ("course_section_id", "subject_name", "day_of_week", "start_period",
                                      "period_count", "classroom", "enrolled", "max_capacity", "lecturer_name",
                                      "grade_status"))
        self.table.pack(fill="both", expand=True, pady=6)
        self.form = FormFields(self, [
            ("subject_id", "Subject ID", subject_ids), ("semester_id", "Semester ID", semester_ids),
            ("classroom", "Classroom"), ("day_of_week", "Day (2-8)"), ("start_period", "Start period (1-12)"),
            ("period_count", "Number of periods"), ("max_capacity", "Maximum capacity"),
            ("lecturer_id", "Lecturer ID (for Assign)")])
        self.form.pack(pady=6)
        buttons = ttk.Frame(self)
        buttons.pack()
        for text, command in [("Open section", self.open_section), ("Assign lecturer", self.assign),
                              ("Remove lecturer", self.unassign), ("Refresh", self.refresh)]:
            ttk.Button(buttons, text=text, command=command).pack(side="left", padx=4)
        self.refresh()

    def refresh(self):
        semester_id = self.semester_filter.get() or None
        data, failed = run(lambda: self.service.list_sections(self.user, semester_id))
        if not failed:
            self.semester_filter.set(data["semester_id"] or "")
            self.table.load(data["sections"])

    def open_section(self):
        v = self.form.get()
        _, failed = run(lambda: self.service.open_section(
            self.user, v["subject_id"], v["semester_id"], v["classroom"], v["day_of_week"], v["start_period"],
            v["period_count"], v["max_capacity"]), "Course section opened.")
        if not failed:
            self.refresh()

    def _selected_section(self):
        row = self.table.selected()
        if row is None:
            messagebox.showinfo("Select", "Please select a course section in the table.")
            return None
        return row["course_section_id"]

    def assign(self):
        section_id = self._selected_section()
        if section_id is not None and confirm("Assign this lecturer to the section?"):
            lecturer_id = self.form.get()["lecturer_id"]
            _, failed = run(lambda: self.service.assign_lecturer(self.user, section_id, lecturer_id), "Lecturer assigned.")
            if not failed:
                self.refresh()

    def unassign(self):
        section_id = self._selected_section()
        if section_id is not None and confirm("Remove the lecturer assignment?"):
            _, failed = run(lambda: self.service.remove_lecturer(self.user, section_id), "Assignment removed.")
            if not failed:
                self.refresh()


class StudentEnrollView(ttk.Frame):
    """UC10 - UC13: dang ky, huy mon, thoi khoa bieu, bang diem da cong bo."""

    def __init__(self, parent, user):
        super().__init__(parent, padding=10)
        self.user = acting_user(user)
        self.service = EnrollService()
        self.schedule = None
        self.semester_id = None

        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Semester").pack(side="left")
        self.semester_box = ttk.Combobox(top, width=12, state="readonly")
        self.semester_box.pack(side="left", padx=4)
        self.semester_box.bind("<<ComboboxSelected>>", lambda event: self.refresh(self.semester_box.get()))
        ttk.Button(top, text="Print timetable", command=self.print_timetable).pack(side="left", padx=4)
        ttk.Button(top, text="Print transcript", command=self.print_transcript).pack(side="left", padx=4)
        ttk.Button(top, text="Refresh", command=lambda: self.refresh(self.semester_box.get() or None)).pack(side="left", padx=4)

        ttk.Label(self, text="Open sections").pack(anchor="w")
        self.open_table = DataTable(self, ("course_section_id", "subject_name", "credits", "day_of_week",
                                           "start_period", "period_count", "classroom", "lecturer_name", "remaining"),
                                    height=6)
        self.open_table.pack(fill="both", expand=True)
        ttk.Button(self, text="Register selected section", command=self.register).pack(pady=4)

        ttk.Label(self, text="Registered courses (timetable)").pack(anchor="w")
        self.reg_table = DataTable(self, ("course_section_id", "subject_name", "credits", "day_of_week",
                                          "start_period", "period_count", "classroom", "lecturer_name"), height=5)
        self.reg_table.pack(fill="both", expand=True)
        ttk.Button(self, text="Cancel selected registration", command=self.drop).pack(pady=4)

        ttk.Label(self, text="Published grades").pack(anchor="w")
        self.grade_table = DataTable(self, ("semester_id", "subject_name", "credits", "process_score",
                                            "exam_score", "final_score", "letter_grade", "result"), height=5)
        self.grade_table.pack(fill="both", expand=True)
        self.refresh(None)

    def refresh(self, semester_id):
        data, failed = run(lambda: self.service.list_open_sections(self.user, semester_id))
        if failed:
            return
        self.semester_id = data["semester_id"]
        self.open_table.load(data["sections"])
        schedule, failed = run(lambda: self.service.view_schedule(self.user, self.semester_id))
        if not failed:
            self.schedule = schedule
            self.reg_table.load(schedule["rows"])
            self.semester_box.config(values=[row["semester_id"] for row in schedule["semesters"]])
            self.semester_box.set(self.semester_id or "")
        grades, failed = run(lambda: self.service.view_grades(self.user, self.semester_id))
        if not failed:
            self.grade_table.load(grades["rows"])

    def register(self):
        row = self.open_table.selected()
        if row is None:
            messagebox.showinfo("Select", "Please select a section in 'Open sections'.")
            return
        _, failed = run(lambda: self.service.register(self.user, row["course_section_id"]), "Registration successful.")
        self.refresh(self.semester_id)

    def drop(self):
        row = self.reg_table.selected()
        if row is None:
            messagebox.showinfo("Select", "Please select a registered course.")
            return
        if confirm("Cancel this registration?"):
            _, failed = run(lambda: self.service.drop(self.user, row["course_section_id"]), "Registration cancelled.")
            self.refresh(self.semester_id)

    def print_timetable(self):
        if self.schedule is None or len(self.schedule["rows"]) == 0:
            messagebox.showinfo("Print", "There is nothing to print.")        # UC12.2.2
            return
        open_html(timetable_html(self.schedule["student"], self.schedule["semester_id"], self.schedule["rows"]),
                  "sms_timetable.html")

    def print_transcript(self):
        data, failed = run(lambda: self.service.view_grades(self.user))
        if failed:
            return
        if len(data["rows"]) == 0:
            messagebox.showinfo("Print", "There is no published grade to print.")   # UC13.2.2
            return
        open_html(transcript_html(data["student"], data["rows"]), "sms_transcript.html")
