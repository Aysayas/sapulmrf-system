from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.users.schemas import Contact, Name, Password


class LoginIn(BaseModel):
    username: str
    password: str


class ProfileIn(BaseModel):
    name: Name | None = None
    contact: Contact | None = None


class PasswordIn(BaseModel):
    current_password: str
    new_password: Password


KioskPin = Annotated[str, StringConstraints(pattern=r"^[0-9]{4,6}$")]


class KioskPinIn(BaseModel):
    pin: KioskPin
