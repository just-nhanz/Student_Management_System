from tkinter import messagebox, ttk

from app.gui.components.widgets import DataTable, FormFields, acting_user, confirm, run
from app.services.catalog_service import CatalogService

# (tieu de tab, khoa trong du lieu, cot hien thi, truong nhap)
TABS = [
    ("Faculties", "faculties", ("faculty_id", "faculty_name", "description", "status"),
     [("faculty_id", "Faculty ID"), ("faculty_name", "Name"), ("description", "Description")]),
    ("Majors", "majors", ("major_id", "major_name", "faculty_id", "status"),
     [("major_id", "Major ID"), ("major_name", "Name"), ("faculty_id", "Faculty ID", [])]),
    ("Classes", "classes", ("class_id", "class_name", "major_id", "academic_year", "status"),
     [("class_id", "Class ID"), ("class_name", "Name"), ("major_id", "Major ID", []), ("academic_year", "Academic year")]),
    ("Subjects", "subjects", ("subject_id", "subject_name", "credits", "faculty_id", "status"),
     [("subject_id", "Subject ID"), ("subject_name", "Name"), ("credits", "Credits (1-10)"),
      ("faculty_id", "Faculty ID", []), ("prerequisites", "Prerequisites (comma-separated IDs)")]),
    ("Semesters", "semesters", ("semester_id", "semester_name", "start_date", "end_date", "reg_start", "reg_end",
                                "cancel_deadline", "max_credits"),
     [("semester_id", "Semester ID"), ("semester_name", "Name"), ("start_date", "Start (YYYY-MM-DD)"),
      ("end_date", "End (YYYY-MM-DD)"), ("reg_start", "Registration start (YYYY-MM-DD HH:MM)"),
      ("reg_end", "Registration end"), ("cancel_deadline", "Cancel deadline"), ("max_credits", "Max credits")]),
]


class CatalogView(ttk.Frame):
    """UC07: khoa, nganh, lop hanh chinh, mon hoc, tien quyet, chuong trinh dao tao, hoc ky."""

    def __init__(self, parent, user):
        super().__init__(parent, padding=10)
        self.user = acting_user(user)
        self.service = CatalogService()
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        self.tables = {}
        self.forms = {}

        for title, key, columns, fields in TABS:
            frame = ttk.Frame(self.notebook, padding=6)
            table = DataTable(frame, columns, height=7)
            table.pack(fill="both", expand=True)
            table.tree.bind("<<TreeviewSelect>>", lambda event, k=key: self.on_select(k))
            form = FormFields(frame, fields)
            form.pack(pady=6)
            buttons = ttk.Frame(frame)
            buttons.pack()
            ttk.Button(buttons, text="Add", command=lambda k=key: self.add(k)).pack(side="left", padx=4)
            ttk.Button(buttons, text="Update", command=lambda k=key: self.update(k)).pack(side="left", padx=4)
            if key != "semesters":
                label = "Discontinue" if key == "subjects" else "Delete / deactivate"
                ttk.Button(buttons, text=label, command=lambda k=key: self.delete(k)).pack(side="left", padx=4)
            ttk.Button(buttons, text="Clear form", command=form.clear).pack(side="left", padx=4)
            self.notebook.add(frame, text=title)
            self.tables[key] = table
            self.forms[key] = form

        # Tab tien quyet
        frame = ttk.Frame(self.notebook, padding=6)
        self.forms["prerequisites"] = FormFields(frame, [
            ("subject_id", "Subject ID", []), ("prerequisites", "Prerequisites (comma-separated IDs)")])
        self.forms["prerequisites"].pack(pady=10)
        ttk.Button(frame, text="Save prerequisites", command=self.save_prerequisites).pack()
        self.notebook.add(frame, text="Prerequisites")

        # Tab chuong trinh dao tao
        frame = ttk.Frame(self.notebook, padding=6)
        self.forms["curriculum"] = FormFields(frame, [
            ("major_id", "Major ID", []), ("subject_id", "Subject ID", []),
            ("is_required", "Type", ["Required", "Elective"]), ("recommended_semester", "Recommended semester")])
        self.forms["curriculum"].pack(pady=10)
        ttk.Button(frame, text="Save curriculum", command=self.save_curriculum).pack()
        self.notebook.add(frame, text="Curriculum")

        self.refresh()

    def refresh(self):
        data, failed = run(lambda: self.service.list_all(self.user))
        if failed:
            return
        for key, table in self.tables.items():
            table.load(data[key])
        faculty_ids = [row["faculty_id"] for row in data["faculties"]]
        major_ids = [row["major_id"] for row in data["majors"]]
        subject_ids = [row["subject_id"] for row in data["subjects"]]
        self.forms["majors"].set_choices("faculty_id", faculty_ids)
        self.forms["classes"].set_choices("major_id", major_ids)
        self.forms["subjects"].set_choices("faculty_id", faculty_ids)
        self.forms["prerequisites"].set_choices("subject_id", subject_ids)
        self.forms["curriculum"].set_choices("major_id", major_ids)
        self.forms["curriculum"].set_choices("subject_id", subject_ids)

    def on_select(self, key):
        row = self.tables[key].selected()
        if row is not None:
            self.forms[key].set(row)

    def _prerequisite_list(self, text):
        ids = []
        for part in text.split(","):
            if part.strip() != "":
                ids.append(part.strip())
        return ids

    def add(self, key):
        v = self.forms[key].get()
        a = self.user
        s = self.service
        if key == "faculties":
            action = lambda: s.add_faculty(a, v["faculty_id"], v["faculty_name"], v["description"])
        elif key == "majors":
            action = lambda: s.add_major(a, v["major_id"], v["major_name"], v["faculty_id"])
        elif key == "classes":
            action = lambda: s.add_class(a, v["class_id"], v["class_name"], v["major_id"], v["academic_year"])
        elif key == "subjects":
            def action():
                s.add_subject(a, v["subject_id"], v["subject_name"], v["credits"], v["faculty_id"])
                ids = self._prerequisite_list(v["prerequisites"])
                if len(ids) > 0:
                    s.set_prerequisites(a, v["subject_id"], ids)
        else:
            action = lambda: s.save_semester(a, v, True)
        _, failed = run(action, "Saved.")
        if not failed:
            self.refresh()

    def update(self, key):
        v = self.forms[key].get()
        a = self.user
        s = self.service
        if key == "faculties":
            action = lambda: s.update_faculty(a, v["faculty_id"], v["faculty_name"], v["description"])
        elif key == "majors":
            action = lambda: s.update_major(a, v["major_id"], v["major_name"], v["faculty_id"])
        elif key == "classes":
            action = lambda: s.update_class(a, v["class_id"], v["class_name"], v["major_id"], v["academic_year"])
        elif key == "subjects":
            def action():
                s.update_subject(a, v["subject_id"], v["subject_name"], v["credits"], v["faculty_id"])
                ids = self._prerequisite_list(v["prerequisites"])
                if len(ids) > 0:
                    s.set_prerequisites(a, v["subject_id"], ids)
        else:
            action = lambda: s.save_semester(a, v, False)
        _, failed = run(action, "Updated.")
        if not failed:
            self.refresh()

    def delete(self, key):
        row = self.tables[key].selected()
        if row is None:
            messagebox.showinfo("Select", "Please select a row in the table.")
            return
        if not confirm("Deactivate the selected entry?"):
            return
        a = self.user
        s = self.service
        if key == "faculties":
            action = lambda: s.delete_faculty(a, row["faculty_id"])
        elif key == "majors":
            action = lambda: s.delete_major(a, row["major_id"])
        elif key == "classes":
            action = lambda: s.delete_class(a, row["class_id"])
        else:
            action = lambda: s.discontinue_subject(a, row["subject_id"])
        _, failed = run(action, "Done.")
        if not failed:
            self.refresh()

    def save_prerequisites(self):
        v = self.forms["prerequisites"].get()
        ids = self._prerequisite_list(v["prerequisites"])
        _, failed = run(lambda: self.service.set_prerequisites(self.user, v["subject_id"], ids), "Prerequisites saved.")

    def save_curriculum(self):
        v = self.forms["curriculum"].get()
        semester = None
        if v["recommended_semester"] != "":
            try:
                semester = int(v["recommended_semester"])
            except ValueError:
                messagebox.showerror("Error", "Recommended semester must be a whole number.")
                return
        run(lambda: self.service.set_curriculum(self.user, v["major_id"], v["subject_id"],
                                                v["is_required"] == "Required", semester), "Curriculum saved.")