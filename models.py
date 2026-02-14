"""SQLAlchemy ORM models."""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    api_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    active_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    topics: Mapped[list["Topic"]] = relationship(back_populates="client", cascade="all, delete-orphan")
    qa_pairs: Mapped[list["QAPair"]] = relationship(back_populates="client", cascade="all, delete-orphan")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="client", cascade="all, delete-orphan")


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    topic_index: Mapped[int] = mapped_column(Integer, nullable=False)
    topic_name: Mapped[str] = mapped_column(String(500), nullable=False)
    semantic_path: Mapped[str | None] = mapped_column(Text)
    original_url: Mapped[str | None] = mapped_column(Text)
    browser_content: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())

    client: Mapped["Client"] = relationship(back_populates="topics")
    qa_pairs: Mapped[list["QAPair"]] = relationship(back_populates="topic", cascade="all, delete-orphan")


class QAPair(Base):
    __tablename__ = "qa_pairs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    topic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    qa_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_bucketed: Mapped[bool] = mapped_column(Boolean, default=False)
    bucket_id: Mapped[str | None] = mapped_column(String(100))
    embedding = mapped_column(Vector(3072))
    combined_hash: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())

    client: Mapped["Client"] = relationship(back_populates="qa_pairs")
    topic: Mapped["Topic"] = relationship(back_populates="qa_pairs")

    __table_args__ = (
        Index("ix_qa_pairs_client_active", "client_id", "is_active"),
        Index("ix_qa_pairs_combined_hash", "client_id", "combined_hash"),
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False)
    user_question: Mapped[str] = mapped_column(Text, nullable=False)
    bot_answer: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    matched_by: Mapped[str] = mapped_column(String(50), default="v3_gemini_qa")
    source_topic: Mapped[str | None] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(Text)
    matched_qa_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("qa_pairs.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.utcnow())

    client: Mapped["Client"] = relationship(back_populates="conversations")

    __table_args__ = (
        Index("ix_conversations_session", "client_id", "session_id", "created_at"),
    )
