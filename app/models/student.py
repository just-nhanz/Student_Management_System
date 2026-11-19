from dataclasses import dataclass
from typing import Optional


@dataclass
class Student:
    student_id: str
    account_id: int
    class_id: str
    date_of_birth: str
    gender: str
    full_name: str = ""
    email: str = ""
    phone_number: Optional[str] = None
    address: Optional[str] = None
    academic_status: str = "STUDYING"
    record_status: str = "ACTIVE"