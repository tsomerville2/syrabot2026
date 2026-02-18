"""Admin endpoints — client management and JSON upload."""

import logging
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_admin_auth
from database import get_db
from models import Client, QAPair, Topic
from schemas import (
    ClientCreate,
    ClientListItem,
    ClientResponse,
    QADeleteRequest,
    QADeleteResponse,
    QAEditRequest,
    QAEditResponse,
    QAPairItem,
    RotateKeyResponse,
    TopicDetail,
    TopicListItem,
    UploadResponse,
)
from services import json_ingestion
from services.embedding import compute_combined_hash, embed_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(get_admin_auth)])


def _generate_api_key() -> str:
    return f"sk-{secrets.token_urlsafe(32)}"


@router.post("/clients", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(body: ClientCreate, db: AsyncSession = Depends(get_db)):
    """Create a new client with a generated API key."""
    # Check uniqueness
    existing = await db.execute(select(Client).where(Client.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Client name already exists")

    client = Client(name=body.name, api_key=_generate_api_key())
    db.add(client)
    await db.commit()
    await db.refresh(client)
    logger.info("Created client %s (%s)", client.name, client.id)
    return client


@router.get("/clients", response_model=list[ClientListItem])
async def list_clients(db: AsyncSession = Depends(get_db)):
    """List all clients (API keys are hidden)."""
    result = await db.execute(select(Client).order_by(Client.created_at))
    return result.scalars().all()


@router.post("/clients/{client_id}/upload", response_model=UploadResponse)
async def upload_json(client_id: uuid.UUID, file: UploadFile, db: AsyncSession = Depends(get_db)):
    """Upload a JSON Q&A file for a client — triggers diff + embedding pipeline."""
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    raw = await file.read()
    try:
        stats = await json_ingestion.ingest(db, client_id, raw)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception:
        logger.exception("Ingestion failed for client %s", client_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Ingestion failed")

    return UploadResponse(
        version=stats.version,
        topics_total=stats.topics_total,
        qa_pairs_total=stats.qa_pairs_total,
        qa_pairs_new=stats.qa_pairs_new,
        qa_pairs_unchanged=stats.qa_pairs_unchanged,
        qa_pairs_removed=stats.qa_pairs_removed,
        errors=stats.errors,
    )


@router.post("/clients/{client_id}/rotate-key", response_model=RotateKeyResponse)
async def rotate_key(client_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Rotate a client's API key."""
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    client.api_key = _generate_api_key()
    await db.commit()
    logger.info("Rotated API key for client %s", client_id)
    return RotateKeyResponse(id=client.id, new_api_key=client.api_key)


# ── Q&A Editor Endpoints ──────────────────────────────────────


@router.get("/clients/{client_id}/topics", response_model=list[TopicListItem])
async def list_topics(client_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """List all active topics for a client with QA pair counts."""
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    stmt = (
        select(
            Topic.id,
            Topic.topic_index,
            Topic.topic_name,
            Topic.semantic_path,
            Topic.original_url,
            func.count(QAPair.id).label("qa_count"),
        )
        .outerjoin(
            QAPair,
            and_(QAPair.topic_id == Topic.id, QAPair.is_active.is_(True)),
        )
        .where(and_(Topic.client_id == client_id, Topic.is_active.is_(True)))
        .group_by(Topic.id)
        .order_by(Topic.topic_index)
    )
    result = await db.execute(stmt)
    return [TopicListItem.model_validate(row._mapping) for row in result.all()]


@router.get("/clients/{client_id}/topics/{topic_id}", response_model=TopicDetail)
async def get_topic_detail(
    client_id: uuid.UUID, topic_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Get a topic with all its active QA pairs."""
    stmt = select(Topic).where(
        and_(Topic.id == topic_id, Topic.client_id == client_id, Topic.is_active.is_(True))
    )
    result = await db.execute(stmt)
    topic = result.scalar_one_or_none()
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")

    qa_stmt = (
        select(QAPair)
        .where(and_(QAPair.topic_id == topic_id, QAPair.is_active.is_(True)))
        .order_by(QAPair.qa_index)
    )
    qa_result = await db.execute(qa_stmt)
    qa_pairs = [QAPairItem.model_validate(row) for row in qa_result.scalars().all()]

    return TopicDetail(
        id=topic.id,
        topic_index=topic.topic_index,
        topic_name=topic.topic_name,
        semantic_path=topic.semantic_path,
        original_url=topic.original_url,
        qa_pairs=qa_pairs,
    )


@router.put("/clients/{client_id}/qa-pairs/{qa_pair_id}", response_model=QAEditResponse)
async def edit_qa_pair(
    client_id: uuid.UUID,
    qa_pair_id: uuid.UUID,
    body: QAEditRequest,
    db: AsyncSession = Depends(get_db),
):
    """Edit a QA pair. Re-embeds only if content hash changes."""
    stmt = select(QAPair).where(
        and_(QAPair.id == qa_pair_id, QAPair.client_id == client_id, QAPair.is_active.is_(True))
    )
    result = await db.execute(stmt)
    qa = result.scalar_one_or_none()
    if qa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QA pair not found")

    old_hash = qa.combined_hash
    new_hash = compute_combined_hash(body.new_question, body.new_answer)

    qa.question = body.new_question
    qa.answer = body.new_answer

    re_embedded = False
    if new_hash != old_hash:
        qa.combined_hash = new_hash
        try:
            combined_text = f"{body.new_question} {body.new_answer}"
            qa.embedding = await embed_document(combined_text)
            re_embedded = True
        except Exception:
            logger.exception("Embedding failed for QA pair %s", qa_pair_id)
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Embedding service failed — changes not saved",
            )

    await db.commit()
    logger.info("Edited QA pair %s (re_embedded=%s)", qa_pair_id, re_embedded)
    return QAEditResponse(
        message="QA pair updated",
        qa_pair_id=qa_pair_id,
        old_hash=old_hash,
        new_hash=new_hash,
        re_embedded=re_embedded,
    )


@router.post("/clients/{client_id}/qa-pairs/delete", response_model=QADeleteResponse)
async def delete_qa_pairs(
    client_id: uuid.UUID, body: QADeleteRequest, db: AsyncSession = Depends(get_db)
):
    """Soft-delete QA pairs by setting is_active=False."""
    stmt = (
        update(QAPair)
        .where(
            and_(
                QAPair.id.in_(body.qa_pair_ids),
                QAPair.client_id == client_id,
                QAPair.is_active.is_(True),
            )
        )
        .values(is_active=False)
    )
    result = await db.execute(stmt)
    await db.commit()

    deleted_count = result.rowcount
    if deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching active QA pairs found",
        )

    logger.info("Soft-deleted %d QA pairs for client %s", deleted_count, client_id)
    return QADeleteResponse(message="QA pairs deleted", deleted_count=deleted_count)
