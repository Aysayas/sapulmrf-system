from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.assistant import service
from app.assistant.service import AskIn, AskOut, ConversationDetail, ConversationOut, FeedbackIn, RenameIn
from app.core.db import get_db
from app.core.deps import require_role
from app.users.models import User

router = APIRouter(prefix="/assistant", tags=["assistant"])
admin_only = require_role("admin")


@router.post("/ask", response_model=AskOut)
def ask(body: AskIn, db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    return service.ask(db, actor, body.text, body.conversation_id, body.intent)


@router.get("/conversations", response_model=list[ConversationOut])
def conversations(db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    return service.conversations(db, actor)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def conversation(conversation_id: int, db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    return service.conversation(db, actor, conversation_id)


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
def rename(conversation_id: int, body: RenameIn, db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    return service.rename(db, actor, conversation_id, body.title)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete(conversation_id: int, db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    service.delete(db, actor, conversation_id)


@router.post("/messages/{message_id}/feedback", status_code=204)
def feedback(message_id: int, body: FeedbackIn, db: DbSession = Depends(get_db), actor: User = Depends(admin_only)):
    service.feedback(db, actor, message_id, body)


@router.get("/suggestions", response_model=list[str])
def suggestions(_: User = Depends(admin_only)):
    return service.suggestions()
