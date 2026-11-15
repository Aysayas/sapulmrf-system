"""Asking: understand the question (topic + slots), answer it, and keep both in the admin's history."""
import re
from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.assistant.answers import answer, unsure
from app.assistant.models import ChatMessage, Conversation
from app.assistant.nlp import INTENTS, SURE, THRESHOLD, Guess, classify, examples
from app.assistant.schemas import Answer
from app.assistant.slots import Slots, extract, load_names, normalize
from app.core.errors import AppError
from app.insights.service import today as local_today
from app.users.models import User

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
# "and purok 4?", "e kahapon?", "how about paper": a follow-up to the last answer's topic
FOLLOW_UP = re.compile(r"^(?:and|at|how about|what about|e|eh|paano naman|kumusta naman|tapos|then)\b")


class AskIn(BaseModel):
    text: Question
    conversation_id: int | None = None
    intent: str | None = None  # a "Did you mean" pick, a correction or "Ask again": skip the classifier


class MessageOut(BaseModel):
    id: int
    role: str
    text: str
    answer: Answer | None
    helpful: bool | None
    created_at: datetime


class AskOut(BaseModel):
    conversation_id: int
    user: MessageOut
    assistant: MessageOut


class ConversationOut(BaseModel):
    id: int
    title: str
    updated_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class RenameIn(BaseModel):
    title: Title


class FeedbackIn(BaseModel):
    helpful: bool
    corrected_intent: str | None = None


def _check_intent(intent: str) -> str:
    if intent not in INTENTS:
        raise AppError(422, f"Unknown topic: {intent}.")
    return intent


def _own(db: DbSession, user: User, conversation_id: int) -> Conversation:
    c = db.get(Conversation, conversation_id)
    if c is None or c.user_id != user.id:
        raise AppError(404, "Chat not found.")
    return c


def _out(m: ChatMessage) -> MessageOut:
    return MessageOut(id=m.id, role=m.role, text=m.text, answer=Answer.model_validate(m.answer) if m.answer else None,
                      helpful=m.helpful, created_at=m.created_at)


def _has_slot(s: Slots) -> bool:
    return any([s.period, s.purok, s.storage_area, s.material, s.category, s.days, s.unknown])


def _merge(new: Slots, old: Slots) -> Slots:
    """A follow-up changes only what it names; the rest comes from the previous question.
    Naming any place replaces all places, so an old "No Purok 99" note doesn't carry over to "and purok 2?"."""
    place = ("purok", "storage_area", "unknown")
    names_a_place = any(getattr(new, k) for k in place)
    keep_new = {"unknown", "bad_dates", "wants", "chat", "text"} | (set(place) if names_a_place else set())
    return Slots(**{k: getattr(new, k) if k in keep_new else getattr(new, k) or getattr(old, k) for k in Slots.model_fields})


def with_hint(a: Answer, guess: Guess) -> Answer:
    """A shaky guess still answers, and offers the other likely topic as the first button."""
    if guess.score >= SURE:
        return a
    return a.model_copy(update={"suggestions": [f"Not what you meant? {examples(guess.runner_up, 1)[0]}", *a.suggestions]})


def ask(db: DbSession, user: User, text: str, conversation_id: int | None = None, intent: str | None = None) -> AskOut:
    conv = _own(db, user, conversation_id) if conversation_id else Conversation(user_id=user.id, title=text[:60])
    previous = None
    if conv.id:
        previous = db.scalar(select(ChatMessage).where(ChatMessage.conversation_id == conv.id, ChatMessage.role == "assistant",
                                                       ChatMessage.intent.in_(INTENTS)).order_by(ChatMessage.id.desc()).limit(1))
    today = local_today()
    slots = extract(text, load_names(db), today)
    guess, follow_up = None, False
    if intent:
        _check_intent(intent)
    else:
        guess = classify(text)
        follow_up = previous is not None and (
            # "and how much did we earn?" is a new topic: a confident guess beats the follow-up word
            (FOLLOW_UP.match(normalize(text)) and (guess.score < SURE or guess.intent == previous.intent))
            or (guess.score < THRESHOLD and _has_slot(slots)))
        if follow_up:
            intent, slots = previous.intent, _merge(slots, Slots.model_validate(previous.slots or {}))
        else:
            intent = guess.intent if guess.score >= THRESHOLD else "unsure"
    if intent == "unsure":
        result = unsure(guess)
    else:
        result = answer(db, intent, slots, today)
        if guess and guess.intent == intent and not follow_up:  # a follow-up's topic isn't in doubt
            result = with_hint(result, guess)

    now = datetime.now(UTC)
    conv.updated_at = now
    db.add(conv)
    db.flush()
    asked = ChatMessage(conversation_id=conv.id, role="user", text=text, created_at=now)
    replied = ChatMessage(conversation_id=conv.id, role="assistant", text=result.title, intent=intent,
                          score=guess.score if guess else None, slots=slots.model_dump(mode="json"),
                          answer=result.model_dump(mode="json"), created_at=now)
    db.add_all([asked, replied])
    db.commit()
    return AskOut(conversation_id=conv.id, user=_out(asked), assistant=_out(replied))


def conversations(db: DbSession, user: User) -> list[ConversationOut]:
    rows = db.scalars(select(Conversation).where(Conversation.user_id == user.id)
                      .order_by(Conversation.updated_at.desc(), Conversation.id.desc()))
    return [ConversationOut(id=c.id, title=c.title, updated_at=c.updated_at) for c in rows]


def conversation(db: DbSession, user: User, conversation_id: int) -> ConversationDetail:
    c = _own(db, user, conversation_id)
    msgs = db.scalars(select(ChatMessage).where(ChatMessage.conversation_id == c.id).order_by(ChatMessage.id))
    return ConversationDetail(id=c.id, title=c.title, updated_at=c.updated_at, messages=[_out(m) for m in msgs])


def rename(db: DbSession, user: User, conversation_id: int, title: str) -> ConversationOut:
    c = _own(db, user, conversation_id)
    c.title = title
    db.commit()
    return ConversationOut(id=c.id, title=c.title, updated_at=c.updated_at)


def delete(db: DbSession, user: User, conversation_id: int) -> None:
    db.delete(_own(db, user, conversation_id))
    db.commit()


def feedback(db: DbSession, user: User, message_id: int, data: FeedbackIn) -> None:
    m = db.get(ChatMessage, message_id)
    if m is None or m.role != "assistant":
        raise AppError(404, "Answer not found.")
    _own(db, user, m.conversation_id)
    m.helpful = data.helpful
    m.corrected_intent = _check_intent(data.corrected_intent) if data.corrected_intent else None
    db.commit()


def suggestions() -> list[str]:
    return [examples(i, 1)[0] for i in ("today", "intake", "storage", "compost", "income", "attention")]
