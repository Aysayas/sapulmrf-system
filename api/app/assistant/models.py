from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Conversation(Base):
    """One admin's chat with Ask SapulMRF. Private to that admin."""

    __tablename__ = "assistant_conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)


class ChatMessage(Base):
    """A question, or the answer to it. The answer is kept as it was shown, so history stays truthful."""

    __tablename__ = "assistant_messages"
    __table_args__ = (CheckConstraint("role IN ('user', 'assistant')", name="ck_assistant_messages_role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("assistant_conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(9))
    text: Mapped[str] = mapped_column(String(500))
    intent: Mapped[str | None] = mapped_column(String(16), default=None)
    score: Mapped[float | None] = mapped_column(Float, default=None)
    slots: Mapped[dict | None] = mapped_column(JSON, default=None)
    answer: Mapped[dict | None] = mapped_column(JSON, default=None)
    helpful: Mapped[bool | None] = mapped_column(default=None)
    corrected_intent: Mapped[str | None] = mapped_column(String(16), default=None)  # what the admin meant, for retraining
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
