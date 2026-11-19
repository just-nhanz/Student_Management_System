from dataclasses import dataclass
from typing import Optional


@dataclass
class TuitionRate:
    rate_id: int
    major_id: str
    semester_id: str
    price_per_credit: float
    effective_from: object
    effective_to: Optional[object] = None
    academic_year: Optional[str] = None


@dataclass
class WaiverPolicy:
    policy_id: int
    policy_name: str
    policy_type: str
    value_type: str
    value: float
    valid_from: object
    valid_to: object
    conditions: Optional[str] = None


@dataclass
class StudentDebt:
    debt_id: int
    student_id: str
    semester_id: str
    total_payable: float
    amount_paid: float
    due_date: object
    status: str
    remaining_debt: float = 0


@dataclass
class PaymentTransaction:
    transaction_id: int
    reference_code: str
    debt_id: int
    transaction_type: str
    amount: float
    method: str
    status: str
    transaction_time: object
    received_by: int
    receipt_no: Optional[str] = None
    original_transaction_id: Optional[int] = None
    reason: Optional[str] = None