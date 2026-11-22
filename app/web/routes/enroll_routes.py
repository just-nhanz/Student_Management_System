from flask import Blueprint, render_template, request

from app.config import ROLE_STUDENT, ROLE_TRAINING
from app.services.catalog_service import CatalogService
from app.services.enroll_service import EnrollService
from app.services.user_service import UserService
from app.utils.export_handler import timetable_html, transcript_html
from app.web import empty_page, login_required, run_service, service_user

bp = Blueprint("enroll", __name__)


@bp.route("/sections", methods=["GET", "POST"])
@login_required(ROLE_TRAINING)
def section_manage():
    """UC08 (mo lop hoc phan) va UC09 (phan cong giang vien)."""
    service = EnrollService()
    actor = service_user()
    f = request.form
    ip = request.remote_addr
    if request.method == "POST":
        action = f.get("action")
        if action == "open":
            run_service(lambda: service.open_section(
                actor, f.get("subject_id"), f.get("semester_id"), f.get("classroom"), f.get("day_of_week"),
                f.get("start_period"), f.get("period_count"), f.get("max_capacity"), ip), "Course section opened.")
        elif action == "assign":
            run_service(lambda: service.assign_lecturer(actor, f.get("section_id"), f.get("lecturer_id"), True, ip),
                        "Lecturer assigned.")
        elif action == "unassign":
            run_service(lambda: service.remove_lecturer(actor, f.get("section_id"), ip), "Assignment removed.")
    semester_id = request.values.get("semester_id")
    sections, _ = run_service(lambda: service.list_sections(actor, semester_id),
                              fallback={"semester_id": semester_id, "sections": []})
    catalog, _ = run_service(lambda: CatalogService().list_all(actor), fallback={"subjects": [], "semesters": []})
    lecturers, _ = run_service(lambda: UserService().search_lecturers(actor, "", 1), fallback=empty_page())
    return render_template("section_manage.html", sections=sections, catalog=catalog, lecturers=lecturers["rows"])


@bp.route("/register", methods=["GET", "POST"])
@login_required(ROLE_STUDENT)
def course_register():
    """UC10 (dang ky) va UC11 (huy mon)."""
    service = EnrollService()
    user = service_user()
    f = request.form
    if request.method == "POST":
        if f.get("action") == "register":
            run_service(lambda: service.register(user, f.get("section_id"), request.remote_addr),
                        "Registration successful.")
        elif f.get("action") == "drop":
            run_service(lambda: service.drop(user, f.get("section_id"), True, request.remote_addr),
                        "Registration cancelled.")
    semester_id = request.values.get("semester_id")
    open_data, _ = run_service(lambda: service.list_open_sections(user, semester_id),
                               fallback={"semester_id": semester_id, "sections": []})
    schedule, _ = run_service(lambda: service.view_schedule(user, open_data["semester_id"]),
                              fallback={"rows": [], "semesters": []})
    return render_template("course_register.html", open_data=open_data, registered=schedule["rows"])


@bp.route("/schedule", methods=["GET"])
@login_required(ROLE_STUDENT)
def schedule_transcript():
    """UC12 (thoi khoa bieu) va UC13 (bang diem da cong bo)."""
    service = EnrollService()
    user = service_user()
    semester_id = request.args.get("semester_id") or None
    schedule, _ = run_service(lambda: service.view_schedule(user, semester_id),
                              fallback={"rows": [], "semesters": [], "semester_id": semester_id})
    grades, _ = run_service(lambda: service.view_grades(user, semester_id), fallback={"rows": []})
    return render_template("schedule_transcript.html", schedule=schedule, grades=grades)


@bp.route("/schedule/print")
@login_required(ROLE_STUDENT)
def print_timetable():
    data, failed = run_service(lambda: EnrollService().view_schedule(service_user(), request.args.get("semester_id")))
    if failed or len(data["rows"]) == 0:
        return "There is nothing to print.", 404       # UC12.2.2
    return timetable_html(data["student"], data["semester_id"], data["rows"])


@bp.route("/transcript/print")
@login_required(ROLE_STUDENT)
def print_transcript():
    data, failed = run_service(lambda: EnrollService().view_grades(service_user(), request.args.get("semester_id")))
    if failed or len(data["rows"]) == 0:
        return "There is no published grade to print.", 404   # UC13.2.2
    return transcript_html(data["student"], data["rows"])
