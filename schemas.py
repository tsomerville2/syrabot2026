"""Pydantic request/response models."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ── Admin: Clients ──────────────────────────────────────────────

class ClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ClientResponse(BaseModel):
    id: uuid.UUID
    name: str
    api_key: str
    is_active: bool
    active_version: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ClientListItem(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    active_version: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Admin: Upload ───────────────────────────────────────────────

class UploadResponse(BaseModel):
    version: int
    topics_total: int
    qa_pairs_total: int
    qa_pairs_new: int
    qa_pairs_unchanged: int
    qa_pairs_removed: int
    errors: list[str] = []


# ── Admin: Rotate Key ──────────────────────────────────────────

class RotateKeyResponse(BaseModel):
    id: uuid.UUID
    new_api_key: str


# ── Chat ────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    session_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    confidence: float
    source_topic: str | None = None
    source_url: str | None = None
    session_id: str
    matched_by: str = "v3_gemini_qa"


# ── Conversations ───────────────────────────────────────────────

class ConversationItem(BaseModel):
    id: uuid.UUID
    user_question: str
    bot_answer: str
    confidence: float
    source_topic: str | None
    source_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationHistory(BaseModel):
    session_id: str
    messages: list[ConversationItem]
    total: int
    page: int
    page_size: int


# ── Health ──────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    database: str
