import time
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

# shortcut: counted per process, fine for one API process. Needs a shared store if it ever runs several workers.
FAILED_LOGINS: dict[str, list[float]] = {}
MAX_FAILURES_PER_IP = 30
IP_WINDOW_S = 300


def _failures_from(ip: str) -> int:
    cutoff = time.monotonic() - IP_WINDOW_S
    recent = [t for t in FAILED_LOGINS.get(ip, []) if t > cutoff]
    if recent:
        FAILED_LOGINS[ip] = recent
    else:
        FAILED_LOGINS.pop(ip, None)
    return len(recent)


def _refuse_if_locked(user: User, now: datetime) -> None:
    if user.locked_until and user.locked_until > now:
        minutes = max(1, round((user.locked_until - now).total_seconds() / 60))
        raise AppError(423, f"Too many wrong passwords. Try again in {minutes} minute{'s' if minutes > 1 else ''}.")


def _count_wrong_password(db: DbSession, user_id: int, now: datetime) -> None:
    user = db.get(User, user_id, with_for_update=True, populate_existing=True)  # parallel guesses must each count
    user.failed_attempts += 1
    if user.failed_attempts >= settings.lockout_attempts:
        user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
        user.failed_attempts = 0
        log(db, user.id, "Account locked", f"{user.username} · {settings.lockout_attempts} wrong passwords")
    db.commit()


def login(db: DbSession, username: str, password: str, ip: str = "") -> tuple[User, str]:
    """Checks the password and opens a session. Returns the user and the cookie token."""
    if _failures_from(ip) >= MAX_FAILURES_PER_IP:
        raise AppError(429, "Too many failed logins from this device. Try again in a few minutes.")
    now = datetime.now(UTC)
    user = db.scalar(select(User).where(User.username == username.strip().lower()))  # usernames are lowercase

    if user:
        _refuse_if_locked(user, now)

    user_id, stored = (user.id, user.password_hash) if user else (None, None)
    db.rollback()  # hashing is slow on purpose, so a flood of logins mustn't hold every database connection
    if not verify_password(password, stored):
        FAILED_LOGINS.setdefault(ip, []).append(time.monotonic())
        if user_id:
            _count_wrong_password(db, user_id, now)
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
    now = datetime.now(UTC)
    _refuse_if_locked(user, now)
    if not verify_password(data.current_password, user.password_hash):
        _count_wrong_password(db, user.id, now)  # same limit as login, or this is an unthrottled password guesser
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


def set_kiosk_pin(db: DbSession, user: User, pin: str) -> None:
    if user.role != "operator":
        raise AppError(403, "Only MRF operators sign in at the kiosk.")
    action = "Changed own kiosk PIN" if user.kiosk_pin_hash else "Set own kiosk PIN"
    user.kiosk_pin_hash = hash_password(pin)
    user.kiosk_pin_failures, user.kiosk_locked_until = 0, None
    log(db, user.id, action)
    db.commit()


def clear_kiosk_pin(db: DbSession, user: User, actor: User) -> None:
    if user.kiosk_pin_hash:
        user.kiosk_pin_hash, user.kiosk_pin_failures, user.kiosk_locked_until = None, 0, None
        log(db, actor.id, "Removed own kiosk PIN" if user.id == actor.id else "Cleared kiosk PIN",
            "" if user.id == actor.id else f"{user.name} ({user.username})")
        db.commit()
