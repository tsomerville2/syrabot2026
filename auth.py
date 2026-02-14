"""Authentication dependencies — admin (env var) and client (DB lookup)."""

import uuid

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from models import Client

bearer_scheme = HTTPBearer()


async def get_admin_auth(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
) -> str:
    """Validate admin API key from Authorization header against env var."""
    if credentials.credentials != settings.admin_api_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin API key")
    return credentials.credentials


async def get_client_from_api_key(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Client:
    """Look up the active client by API key."""
    result = await db.execute(
        select(Client).where(Client.api_key == credentials.credentials, Client.is_active == True)  # noqa: E712
    )
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or inactive API key")
    return client
