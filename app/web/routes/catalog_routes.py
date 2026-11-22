from flask import Blueprint, render_template, request

from app.config import ROLE_TRAINING
from app.services.catalog_service import CatalogService
from app.web import login_required, run_service, service_user

bp = Blueprint("catalog", __name__)


@bp.route("/catalog", methods=["GET", "POST"])
@login_required(ROLE_TRAINING)
def catalog():
    """UC07: quan ly danh muc khoa / nganh / lop / mon hoc / tien quyet / chuong trinh / hoc ky."""
    service = CatalogService()
    actor = service_user()
    if request.method == "POST":
        f = request.form
        action = f.get("action")
        if action == "add_faculty":
            run_service(lambda: service.add_faculty(actor, f.get("faculty_id"), f.get("faculty_name"),
                                                    f.get("description")), "Faculty added.")
        elif action == "delete_faculty":
            run_service(lambda: service.delete_faculty(actor, f.get("faculty_id")), "Faculty deactivated.")
        elif action == "add_major":
            run_service(lambda: service.add_major(actor, f.get("major_id"), f.get("major_name"),
                                                  f.get("faculty_id")), "Major added.")
        elif action == "delete_major":
            run_service(lambda: service.delete_major(actor, f.get("major_id")), "Major deactivated.")
        elif action == "add_class":
            run_service(lambda: service.add_class(actor, f.get("class_id"), f.get("class_name"), f.get("major_id"),
                                                  f.get("academic_year")), "Class added.")
        elif action == "delete_class":
            run_service(lambda: service.delete_class(actor, f.get("class_id")), "Class deactivated.")
        elif action == "add_subject":
            run_service(lambda: service.add_subject(actor, f.get("subject_id"), f.get("subject_name"),
                                                    f.get("credits"), f.get("faculty_id")), "Subject added.")
        elif action == "discontinue_subject":
            run_service(lambda: service.discontinue_subject(actor, f.get("subject_id")), "Subject discontinued.")
        elif action == "set_prerequisites":
            ids = [x.strip() for x in (f.get("prerequisites") or "").split(",") if x.strip() != ""]
            run_service(lambda: service.set_prerequisites(actor, f.get("subject_id"), ids), "Prerequisites saved.")
        elif action == "set_curriculum":
            run_service(lambda: service.set_curriculum(
                actor, f.get("major_id"), f.get("subject_id"), f.get("is_required") == "1",
                int(f.get("recommended_semester") or 0)), "Curriculum saved.")
        elif action == "add_semester":
            run_service(lambda: service.save_semester(actor, f.to_dict(), True), "Semester added.")
    data, _ = run_service(lambda: service.list_all(actor),
                          fallback={"faculties": [], "majors": [], "classes": [], "subjects": [], "semesters": []})
    return render_template("catalog_manage.html", data=data)