from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class User:
    """Lop truu tuong User -> bang account + account_role."""
    account_id: int
    username: str
    full_name: str
    email: str
    status: str = "ACTIVE"
    phone_number: Optional[str] = None
    must_change_password: bool = False
    roles: List[str] = field(default_factory=list)

    def has_role(self, role_name):
        return role_name in self.roles


@dataclass
class Admin(User):
    admin_id: str = ""