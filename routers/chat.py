"""Chat and conversation history endpoints."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_client_from_api_key
from database import get_db
from models import Client, Conversation
from schemas import (
    ChatRequest,
    ChatResponse,
    ConversationHistory,
    ConversationItem,
    HealthResponse,
)
from services import search as search_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    client: Client = Depends(get_client_from_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Answer a user question using pgvector similarity search."""
    session_id = body.session_id or str(uuid.uuid4())

    results = await search_service.search(db, client.id, body.question, top_k=1)

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No QA data found for this client. Upload a JSON file first.",
        )

    best = results[0]

    # Persist conversation turn
    conv = Conversation(
        client_id=client.id,
        session_id=session_id,
        user_question=body.question,
        bot_answer=best["answer"],
        confidence=best["similarity"],
        matched_by="v3_gemini_qa",
        source_topic=best["source_topic"],
        source_url=best["source_url"],
        matched_qa_id=best["qa_id"],
    )
    db.add(conv)
    await db.commit()

    return ChatResponse(
        answer=best["answer"],
        confidence=best["similarity"],
        source_topic=best["source_topic"],
        source_url=best["source_url"],
        session_id=session_id,
        matched_qa_id=best["qa_id"],
        matched_topic_id=best["topic_id"],
    )


@router.get("/conversations/{session_id}", response_model=ConversationHistory)
async def get_conversations(
    session_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    client: Client = Depends(get_client_from_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated conversation history for a session."""
    base_filter = (
        select(Conversation)
        .where(Conversation.client_id == client.id, Conversation.session_id == session_id)
        .order_by(Conversation.created_at)
    )

    # Count total
    count_q = select(func.count()).select_from(base_filter.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginate
    rows = (
        await db.execute(base_filter.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()

    return ConversationHistory(
        session_id=session_id,
        messages=[ConversationItem.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/health", response_model=HealthResponse)
async def health(db: AsyncSession = Depends(get_db)):
    """Health check — verifies DB connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "unavailable"

    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        database=db_status,
    )
