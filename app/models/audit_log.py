from dataclasses import dataclass
from typing import Optional


@dataclass
class AuditLog:
    log_id: int
    action: str
    created_at: object
    account_id: Optional[int] = None
    object_type: Optional[str] = None
    object_id: Optional[str] = None
    detail: Optional[str] = None
    ip_address: Optional[str] = None