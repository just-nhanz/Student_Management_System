from dataclasses import dataclass
from typing import Optional


@dataclass
class Faculty:
    faculty_id: str
    faculty_name: str
    description: Optional[str] = None
    status: str = "ACTIVE"


@dataclass
class Major:
    major_id: str
    major_name: str
    faculty_id: str
    status: str = "ACTIVE"


@dataclass
class AdministrativeClass:
    class_id: str
    class_name: str
    major_id: str
    academic_year: str
    status: str = "ACTIVE"


@dataclass
class Subject:
    subject_id: str
    subject_name: str
    credits: int
    faculty_id: str
    status: str = "ACTIVE"


@dataclass
class CurriculumSubject:
    major_id: str
    subject_id: str
    is_required: bool = True
    recommended_semester: Optional[int] = None


@dataclass
class Semester:
    semester_id: str
    semester_name: str
    start_date: object
    end_date: object
    reg_start: object
    reg_end: object
    cancel_deadline: object
    max_credits: int = 24