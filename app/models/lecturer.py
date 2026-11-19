from dataclasses import dataclass
from typing import Optional


@dataclass
class Lecturer:
    lecturer_id: str
    account_id: int
    faculty_id: str
    full_name: str = ""
    email: str = ""
    phone_number: Optional[str] = None
    degree: Optional[str] = None
    specialization: Optional[str] = None
    employment_status: str = "ACTIVE"