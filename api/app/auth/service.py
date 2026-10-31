from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from app.activity.service import log
from app.auth.models import Session
from app.auth.schemas import PasswordIn, ProfileIn
from app.core.config import settings
from app.core.errors import AppError
from app.core.security import hash_password, new_session_token, token_hash, verify_password
from app.users.models import User


def login(db: DbSession, username: str, password: str) -> tuple[User, str]:
    """Checks the password and opens a session. Returns the user and the cookie token."""
    now = datetime.now(UTC)
    user = db.scalar(select(User).where(User.username == username.strip().lower()))  # usernames are lowercase

    if user and user.locked_until and user.locked_until > now:
        minutes = max(1, round((user.locked_until - now).total_seconds() / 60))
        raise AppError(423, f"Too many wrong passwords. Try again in {minutes} minute{'s' if minutes > 1 else ''}.")

    if not verify_password(password, user.password_hash if user else None):
        if user:
            user.failed_attempts += 1
            if user.failed_attempts >= settings.lockout_attempts:
                user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
                user.failed_attempts = 0
                log(db, user.id, "Account locked", f"{user.username} · {settings.lockout_attempts} wrong passwords")
            db.commit()
        raise AppError(401, "Wrong username or password.")

    if not user.active:
        raise AppError(403, "This account is disabled. Ask the administrator.")

    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    db.execute(delete(Session).where(Session.expires_at <= now))
    token, hashed = new_session_token()
    db.add(Session(token_hash=hashed, user_id=user.id, expires_at=now + timedelta(hours=settings.session_hours)))
    log(db, user.id, "Logged in")
    db.commit()
    return user, token


def update_profile(db: DbSession, user: User, data: ProfileIn) -> User:
    changed = []
    for field in ("name", "contact"):
        value = getattr(data, field)
        if value is not None and value != getattr(user, field):
            setattr(user, field, value)
            changed.append(field)
    if changed:
        log(db, user.id, "Updated own profile", ", ".join(changed))
        db.commit()
    return user


def change_password(db: DbSession, user: User, data: PasswordIn, token: str | None) -> None:
    if not verify_password(data.current_password, user.password_hash):
        raise AppError(400, "Your current password is wrong.")  # not 401: the session is still good
    if data.new_password == data.current_password:
        raise AppError(422, "Pick a password different from the current one.")
    user.password_hash = hash_password(data.new_password)
    user.failed_attempts, user.locked_until = 0, None
    # Sign out every other browser, keeping this one.
    db.execute(delete(Session).where(Session.user_id == user.id, Session.token_hash != token_hash(token or "")))
    log(db, user.id, "Changed own password")
    db.commit()


def logout(db: DbSession, token: str | None) -> None:
    s = db.scalar(select(Session).where(Session.token_hash == token_hash(token))) if token else None
    if s:
        log(db, s.user_id, "Logged out")
        db.delete(s)
        db.commit()
