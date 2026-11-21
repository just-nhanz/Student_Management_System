from app.config import Config, ROLE_TRAINING
from app.repositories.catalog_repo import CatalogRepo
from app.services import ServiceError, parse_date, parse_datetime, require_role, validation_error
from app.utils.database import Database


class CatalogService:
    """UC07: khoa, nganh, lop hanh chinh, mon hoc (tien quyet, chuong trinh), hoc ky."""

    def __init__(self, connection=None):
        self.connection = connection

    def _db(self):
        return Database(self.connection)

    def list_all(self, actor):
        require_role(actor, ROLE_TRAINING)
        with self._db() as db:
            catalog = CatalogRepo(db)
            return {"faculties": catalog.list_faculties(), "majors": catalog.list_majors(),
                    "classes": catalog.list_classes(), "subjects": catalog.list_subjects(),
                    "semesters": catalog.list_semesters()}

    # ---------------------------------------------------------------- faculty
    def add_faculty(self, actor, faculty_id, faculty_name, description=""):
        require_role(actor, ROLE_TRAINING)
        errors = self._need({"faculty_id": faculty_id, "faculty_name": faculty_name})
        if errors:
            raise validation_error(errors)
        with self._db() as db:
            catalog = CatalogRepo(db)
            # UC07.2.2: ma bi trung
            if catalog.find_faculty(faculty_id) is not None or catalog.find_faculty_by_name(faculty_name) is not None:
                raise ServiceError("Faculty ID or name already exists.")
            catalog.insert_faculty(faculty_id.strip(), faculty_name.strip(), description or None)
        return True

    def update_faculty(self, actor, faculty_id, faculty_name, description=""):
        require_role(actor, ROLE_TRAINING)
        errors = self._need({"faculty_name": faculty_name})
        if errors:
            raise validation_error(errors)
        with self._db() as db:
            catalog = CatalogRepo(db)
            if catalog.find_faculty(faculty_id) is None:
                raise ServiceError("Faculty not found.")
            other = catalog.find_faculty_by_name(faculty_name)
            if other is not None and other["faculty_id"] != faculty_id:
                raise ServiceError("Faculty name already exists.")
            catalog.update_faculty(faculty_id, faculty_name.strip(), description or None)
        return True

    def delete_faculty(self, actor, faculty_id, confirmed=True):
        require_role(actor, ROLE_TRAINING)
        if not confirmed:
            return False
        with self._db() as db:
            catalog = CatalogRepo(db)
            if catalog.find_faculty(faculty_id) is None:
                raise ServiceError("Faculty not found.")
            # UC07.2.2: con nganh / giang vien / mon hoc phu thuoc thi khong vo hieu hoa
            if catalog.faculty_dependents(faculty_id) > 0:
                raise ServiceError("The faculty still has majors, lecturers or subjects. Handle them first.")
            catalog.set_faculty_status(faculty_id, "INACTIVE")  # BR-02
        return True

    # ---------------------------------------------------------------- major
    def add_major(self, actor, major_id, major_name, faculty_id):
        require_role(actor, ROLE_TRAINING)
        errors = self._need({"major_id": major_id, "major_name": major_name})
        if errors:
            raise validation_error(errors)
        with self._db() as db:
            catalog = CatalogRepo(db)
            if catalog.find_major(major_id) is not None:
                raise ServiceError("Major ID already exists.")
            faculty = catalog.find_faculty(faculty_id or "")
            if faculty is None or faculty["status"] != "ACTIVE":
                raise ServiceError("The owning faculty does not exist.")  # SRS: moi nganh thuoc mot khoa hop le
            catalog.insert_major(major_id.strip(), major_name.strip(), faculty_id)
        return True

    def update_major(self, actor, major_id, major_name, faculty_id):
        require_role(actor, ROLE_TRAINING)
        with self._db() as db:
            catalog = CatalogRepo(db)
            if catalog.find_major(major_id) is None:
                raise ServiceError("Major not found.")
            if (major_name or "").strip() == "":
                raise validation_error({"major_name": "Required."})
            if catalog.find_faculty(faculty_id or "") is None:
                raise ServiceError("The owning faculty does not exist.")
            catalog.update_major(major_id, major_name.strip(), faculty_id)
        return True

    def delete_major(self, actor, major_id, confirmed=True):
        require_role(actor, ROLE_TRAINING)
        if not confirmed:
            return False
        with self._db() as db:
            catalog = CatalogRepo(db)
            if catalog.find_major(major_id) is None:
                raise ServiceError("Major not found.")
            if catalog.major_dependents(major_id) > 0:
                raise ServiceError("The major still has administrative classes. Handle them first.")
            catalog.set_major_status(major_id, "INACTIVE")
        return True

    # ---------------------------------------------------------------- administrative class
    def add_class(self, actor, class_id, class_name, major_id, academic_year):
        require_role(actor, ROLE_TRAINING)
        errors = self._need({"class_id": class_id, "class_name": class_name, "academic_year": academic_year})
        if errors:
            raise validation_error(errors)
        with self._db() as db:
            catalog = CatalogRepo(db)
            if catalog.find_class(class_id) is not None:
                raise ServiceError("Class ID already exists.")
            major = catalog.find_major(major_id or "")
            if major is None or major["status"] != "ACTIVE":
                raise ServiceError("The major does not exist.")
            catalog.insert_class(class_id.strip(), class_name.strip(), major_id, academic_year.strip())
        return True

    def update_class(self, actor, class_id, class_name, major_id, academic_year):
        require_role(actor, ROLE_TRAINING)
        with self._db() as db:
            catalog = CatalogRepo(db)
            if catalog.find_class(class_id) is None:
                raise ServiceError("Class not found.")
            if catalog.find_major(major_id or "") is None:
                raise ServiceError("The major does not exist.")
            errors = self._need({"class_name": class_name, "academic_year": academic_year})
            if errors:
                raise validation_error(errors)
            catalog.update_class(class_id, class_name.strip(), major_id, academic_year.strip())
        return True

    def delete_class(self, actor, class_id, confirmed=True):
        require_role(actor, ROLE_TRAINING)
        if not confirmed:
            return False
        with self._db() as db:
            catalog = CatalogRepo(db)
            if catalog.find_class(class_id) is None:
                raise ServiceError("Class not found.")
            # UC07.3: xoa lop khong duoc lam mat lien ket sinh vien - lop
            if catalog.class_dependents(class_id) > 0:
                raise ServiceError("The class contains students. Transfer them first.")
            catalog.set_class_status(class_id, "INACTIVE")
        return True

    # ---------------------------------------------------------------- subject
    def add_subject(self, actor, subject_id, subject_name, credits, faculty_id):
        require_role(actor, ROLE_TRAINING)
        errors = self._need({"subject_id": subject_id, "subject_name": subject_name})
        credits = self._parse_credits(credits, errors)
        if errors:
            raise validation_error(errors)
        with self._db() as db:
            catalog = CatalogRepo(db)
            if catalog.find_subject(subject_id) is not None:
                raise ServiceError("Subject ID already exists.")
            if catalog.find_faculty(faculty_id or "") is None:
                raise ServiceError("The managing faculty does not exist.")
            catalog.insert_subject(subject_id.strip(), subject_name.strip(), credits, faculty_id)
        return True

    def update_subject(self, actor, subject_id, subject_name, credits, faculty_id):
        require_role(actor, ROLE_TRAINING)
        errors = self._need({"subject_name": subject_name})
        credits = self._parse_credits(credits, errors)
        if errors:
            raise validation_error(errors)
        with self._db() as db:
            catalog = CatalogRepo(db)
            if catalog.find_subject(subject_id) is None:
                raise ServiceError("Subject not found.")
            if catalog.find_faculty(faculty_id or "") is None:
                raise ServiceError("The managing faculty does not exist.")
            catalog.update_subject(subject_id, subject_name.strip(), credits, faculty_id)
        return True

    def discontinue_subject(self, actor, subject_id, confirmed=True):
        """UC07.2.2: mon hoc da dung trong lop hoc phan -> DISCONTINUED, khong mo lop moi."""
        require_role(actor, ROLE_TRAINING)
        if not confirmed:
            return False
        with self._db() as db:
            catalog = CatalogRepo(db)
            if catalog.find_subject(subject_id) is None:
                raise ServiceError("Subject not found.")
            catalog.set_subject_status(subject_id, "DISCONTINUED")
        return True

    def set_prerequisites(self, actor, subject_id, prerequisite_ids):
        """UC07: dat danh sach mon tien quyet; tu chon chinh no hoac tao vong lap bi tu choi."""
        require_role(actor, ROLE_TRAINING)
        with self._db() as db:
            catalog = CatalogRepo(db)
            if catalog.find_subject(subject_id) is None:
                raise ServiceError("Subject not found.")
            for prerequisite_id in prerequisite_ids:
                if prerequisite_id == subject_id:
                    raise ServiceError("A subject cannot be its own prerequisite.")
                if catalog.find_subject(prerequisite_id) is None:
                    raise ServiceError("Prerequisite subject %s does not exist." % prerequisite_id)
                if self._reaches(catalog, prerequisite_id, subject_id):
                    raise ServiceError("Circular prerequisite chain detected with %s." % prerequisite_id)
            for old in catalog.list_prerequisites(subject_id):
                if old not in prerequisite_ids:
                    catalog.remove_prerequisite(subject_id, old)
            for prerequisite_id in prerequisite_ids:
                catalog.add_prerequisite(subject_id, prerequisite_id)
        return True

    def _reaches(self, catalog, start_id, target_id):
        """Duyet theo chieu sau: tu start_id co di den target_id qua chuoi tien quyet khong?"""
        stack = [start_id]
        visited = []
        while len(stack) > 0:
            current = stack.pop()
            if current == target_id:
                return True
            if current in visited:
                continue
            visited.append(current)
            for next_id in catalog.list_prerequisites(current):
                stack.append(next_id)
        return False

    def set_curriculum(self, actor, major_id, subject_id, is_required, recommended_semester):
        require_role(actor, ROLE_TRAINING)
        with self._db() as db:
            catalog = CatalogRepo(db)
            if catalog.find_major(major_id) is None or catalog.find_subject(subject_id) is None:
                raise ServiceError("Major or subject does not exist.")
            catalog.set_curriculum(major_id, subject_id, 1 if is_required else 0, recommended_semester or None)
        return True

    # ---------------------------------------------------------------- semester
    def save_semester(self, actor, data, is_new=True):
        require_role(actor, ROLE_TRAINING)
        errors = self._need({"semester_id": data.get("semester_id"), "semester_name": data.get("semester_name")})
        if errors:
            raise validation_error(errors)
        start_date = parse_date(data.get("start_date"), "start_date")
        end_date = parse_date(data.get("end_date"), "end_date")
        reg_start = parse_datetime(data.get("reg_start"), "reg_start")
        reg_end = parse_datetime(data.get("reg_end"), "reg_end")
        cancel_deadline = parse_datetime(data.get("cancel_deadline"), "cancel_deadline")
        try:
            max_credits = int(data.get("max_credits") or Config.DEFAULT_MAX_CREDITS)
        except ValueError:
            raise validation_error({"max_credits": "Must be a number."})
        # UC07.2.2: ngay ket thuc phai sau ngay bat dau, moc dang ky phai nhat quan
        if not start_date < end_date:
            raise ServiceError("The end date must be after the start date.")
        if not reg_start < reg_end:
            raise ServiceError("The registration start must be before the registration end.")
        if cancel_deadline < reg_start:
            raise ServiceError("The cancellation deadline must not be before the registration start.")
        if max_credits < 1:
            raise validation_error({"max_credits": "Must be positive."})
        with self._db() as db:
            catalog = CatalogRepo(db)
            exists = catalog.find_semester(data["semester_id"]) is not None
            if is_new and exists:
                raise ServiceError("Semester ID already exists.")
            if not is_new and not exists:
                raise ServiceError("Semester not found.")
            args = (data["semester_id"].strip(), data["semester_name"].strip(), start_date, end_date, reg_start,
                    reg_end, cancel_deadline, max_credits)
            if is_new:
                catalog.insert_semester(*args)
            else:
                catalog.update_semester(*args)
        return True

    def delete_semester(self, actor, semester_id):
        """BR-02: hoc ky la du lieu lich su, khong xoa vat ly."""
        require_role(actor, ROLE_TRAINING)
        with self._db() as db:
            if CatalogRepo(db).semester_dependents(semester_id) > 0:
                raise ServiceError("The semester has course sections or registrations and cannot be deleted.")
        raise ServiceError("Semesters are kept for history and are never deleted; edit its dates instead.")

    # ---------------------------------------------------------------- helpers
    def _need(self, fields):
        errors = {}
        for name, value in fields.items():
            if (value or "").strip() == "":
                errors[name] = "Required."
        return errors

    def _parse_credits(self, credits, errors):
        try:
            value = int(credits)
        except (TypeError, ValueError):
            errors["credits"] = "Must be a whole number."
            return None
        if value < 1 or value > 10:
            errors["credits"] = "Must be between 1 and 10."
        return value