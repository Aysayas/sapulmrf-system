from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Role = Literal["admin", "operator", "staff"]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
# Lowercased before saving; the pattern accepts either case because Pydantic checks it before lowering.
Username = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[A-Za-z0-9._-]{3,60}$")]
Password = Annotated[str, Field(min_length=8, max_length=128)]
Contact = Annotated[str, StringConstraints(strip_whitespace=True, max_length=30, pattern=r"^[0-9+() -]*$")]


class UserOut(BaseModel):
    """What the API shows about a user. Never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    contact: str
    username: str
    role: Role
    active: bool
    has_kiosk_pin: bool = False
    last_login_at: datetime | None
    created_at: datetime


class UserCreate(BaseModel):
    name: Name
    username: Username
    role: Role
    password: Password


class UserUpdate(BaseModel):
    name: Name | None = None
    username: Username | None = None
    role: Role | None = None
    active: bool | None = None
    password: Password | None = None
