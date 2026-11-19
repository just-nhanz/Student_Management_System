# Cac enumeration cua SRS 6.4. Dung hang so chuoi don gian de de bao ve.

class AccountStatus:
    ACTIVE = "ACTIVE"
    LOCKED = "LOCKED"


class AcademicStatus:
    STUDYING = "STUDYING"
    ON_LEAVE = "ON_LEAVE"
    DROPPED_OUT = "DROPPED_OUT"
    GRADUATED = "GRADUATED"


class RegistrationStatus:
    PENDING = "PENDING"
    SUCCESSFUL = "SUCCESSFUL"
    CANCELLED = "CANCELLED"


class DebtStatus:
    UNPAID = "UNPAID"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    COMPLETED = "COMPLETED"
    OVERDUE = "OVERDUE"


class GradeStatus:
    UNLOCKED = "UNLOCKED"
    LOCKED = "LOCKED"
    PUBLISHED = "PUBLISHED"


class SectionStatus:
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class TransactionType:
    PAYMENT = "PAYMENT"
    REFUND = "REFUND"
    ADJUSTMENT = "ADJUSTMENT"


class TransactionStatus:
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"


class PaymentMethod:
    CASH = "CASH"
    BANK_TRANSFER = "BANK_TRANSFER"