from datetime import UTC, datetime

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.auth.models import Session
from app.core.db import get_db
from app.core.errors import AppError
from app.core.security import token_hash
from app.users.models import User

COOKIE = "sapulmrf_session"


def current_user(request: Request, db: DbSession = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE)
    s = db.scalar(select(Session).where(Session.token_hash == token_hash(token))) if token else None
    user = db.get(User, s.user_id) if s and s.expires_at > datetime.now(UTC) else None
    if not user or not user.active:
        raise AppError(401, "Log in first.")
    return user


def require_role(*roles: str):
    def check(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise AppError(403, "Your role can't do this.")
        return user

    return check
