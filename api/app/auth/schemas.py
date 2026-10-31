from pydantic import BaseModel

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
