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


# ── Admin: Q&A Editor ─────────────────────────────────────────

class QAEditRequest(BaseModel):
    new_question: str = Field(..., min_length=1)
    new_answer: str = Field(..., min_length=1)


class QADeleteRequest(BaseModel):
    qa_pair_ids: list[uuid.UUID] = Field(..., min_length=1)


class TopicListItem(BaseModel):
    id: uuid.UUID
    topic_index: int
    topic_name: str
    semantic_path: str | None
    original_url: str | None
    qa_count: int

    model_config = {"from_attributes": True}


class QAPairItem(BaseModel):
    id: uuid.UUID
    qa_index: int
    question: str
    answer: str
    is_bucketed: bool
    bucket_id: str | None
    combined_hash: str

    model_config = {"from_attributes": True}


class TopicDetail(BaseModel):
    id: uuid.UUID
    topic_index: int
    topic_name: str
    semantic_path: str | None
    original_url: str | None
    qa_pairs: list[QAPairItem]

    model_config = {"from_attributes": True}


class QAEditResponse(BaseModel):
    message: str
    qa_pair_id: uuid.UUID
    old_hash: str
    new_hash: str
    re_embedded: bool


class QADeleteResponse(BaseModel):
    message: str
    deleted_count: int


# ── Password Login ─────────────────────────────────────────────

class PasswordLoginRequest(BaseModel):
    password: str = Field(..., min_length=1)


class PasswordLoginResponse(BaseModel):
    client_api_key: str
    client_name: str
    client_id: str
    admin_api_key: str


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
    matched_qa_id: uuid.UUID | None = None
    matched_topic_id: uuid.UUID | None = None


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
