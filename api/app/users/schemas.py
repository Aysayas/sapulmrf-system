from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

Role = Literal["admin", "operator", "staff"]


class UserOut(BaseModel):
    """What the API shows about a user. Never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    username: str
    role: Role
    active: bool
    last_login_at: datetime | None
    created_at: datetime
