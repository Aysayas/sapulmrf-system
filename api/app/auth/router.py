from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session as DbSession

from app.auth import service
from app.auth.schemas import LoginIn, PasswordIn, ProfileIn
from app.core.config import settings
from app.core.db import get_db
from app.core.deps import COOKIE, current_user
from app.users.models import User
from app.users.schemas import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, response: Response, db: DbSession = Depends(get_db)):
    user, token = service.login(db, body.username, body.password)
    response.set_cookie(COOKIE, token, max_age=settings.session_hours * 3600, httponly=True, samesite="lax",
                        secure=settings.cookie_secure, path="/")
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: DbSession = Depends(get_db)):
    service.logout(db, request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE, path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: ProfileIn, db: DbSession = Depends(get_db), user: User = Depends(current_user)):
    return service.update_profile(db, user, body)


@router.post("/me/password", status_code=204)
def change_my_password(body: PasswordIn, request: Request, db: DbSession = Depends(get_db),
                       user: User = Depends(current_user)):
    service.change_password(db, user, body, request.cookies.get(COOKIE))
