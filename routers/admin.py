"""Admin endpoints — client management and JSON upload."""

import logging
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_admin_auth
from database import get_db
from models import Client
from schemas import (
    ClientCreate,
    ClientListItem,
    ClientResponse,
    RotateKeyResponse,
    UploadResponse,
)
from services import json_ingestion

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
