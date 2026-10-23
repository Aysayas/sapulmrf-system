from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from app.activity.service import log
from app.auth.models import Session
from app.core.config import settings
from app.core.errors import AppError
from app.core.security import new_session_token, token_hash, verify_password
from app.users.models import User


def login(db: DbSession, username: str, password: str) -> tuple[User, str]:
    """Checks the password and opens a session. Returns the user and the cookie token."""
    now = datetime.now(UTC)
    user = db.scalar(select(User).where(User.username == username.strip()))

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


def logout(db: DbSession, token: str | None) -> None:
    s = db.scalar(select(Session).where(Session.token_hash == token_hash(token))) if token else None
    if s:
        log(db, s.user_id, "Logged out")
        db.delete(s)
        db.commit()
