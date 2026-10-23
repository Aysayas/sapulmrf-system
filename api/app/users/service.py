from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from app.activity.service import log
from app.auth.models import Session
from app.core.errors import AppError
from app.core.security import hash_password
from app.users.models import User
from app.users.schemas import UserCreate, UserUpdate


def list_users(db: DbSession) -> list[User]:
    return list(db.scalars(select(User).order_by(User.name)))


def _username_taken(db: DbSession, username: str, except_id: int | None = None) -> bool:
    q = select(User.id).where(User.username == username)
    if except_id is not None:
        q = q.where(User.id != except_id)
    return db.scalar(q) is not None


def create_user(db: DbSession, data: UserCreate, actor: User) -> User:
    if _username_taken(db, data.username):
        raise AppError(409, "That username is taken.")
    user = User(name=data.name, username=data.username, role=data.role, password_hash=hash_password(data.password))
    db.add(user)
    db.flush()
    log(db, actor.id, "Created user", f"{user.name} ({user.username}) · {user.role}")
    db.commit()
    return user


def update_user(db: DbSession, user_id: int, data: UserUpdate, actor: User) -> User:
    user = db.get(User, user_id)
    if not user:
        raise AppError(404, "User not found.")
    if user.id == actor.id and (data.active is False or (data.role and data.role != user.role)):
        raise AppError(400, "You can't disable your own account or change your own role.")
    if data.username and _username_taken(db, data.username, except_id=user.id):
        raise AppError(409, "That username is taken.")

    changes = data.model_dump(exclude_unset=True, exclude={"password"})
    for field, value in changes.items():
        setattr(user, field, value)
    if data.password:
        user.password_hash = hash_password(data.password)
        user.failed_attempts, user.locked_until = 0, None
    if data.password or data.active is False:
        db.execute(delete(Session).where(Session.user_id == user.id))  # sign them out everywhere

    record = f"{user.name} ({user.username})"
    if data.active is False:
        log(db, actor.id, "Disabled user", record)
    elif data.active is True and len(changes) == 1:
        log(db, actor.id, "Enabled user", record)
    elif data.password and not changes:
        log(db, actor.id, "Reset password", record)
    else:
        fields = sorted(changes) + (["password"] if data.password else [])
        log(db, actor.id, "Edited user", f"{record} · {', '.join(fields)}")
    db.commit()
    return user
