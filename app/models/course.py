from dataclasses import dataclass
from typing import Optional


@dataclass
class CourseSection:
    course_section_id: str
    subject_id: str
    semester_id: str
    section_no: int
    day_of_week: int
    start_period: int
    period_count: int
    max_capacity: int
    lecturer_id: Optional[str] = None
    classroom: Optional[str] = None
    status: str = "OPEN"
    grade_status: str = "UNLOCKED"


@dataclass
class CourseRegistration:
    registration_id: int
    student_id: str
    course_section_id: str
    status: str
    registration_date: object = None
    cancelled_at: object = None


@dataclass
class Grade:
    grade_id: int
    registration_id: int
    process_score: Optional[float] = None
    exam_score: Optional[float] = None
    final_score: Optional[float] = None
    letter_grade: Optional[str] = None
    version: int = 0