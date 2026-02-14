"""Gemini embedding service — wraps genai.embed_content for async use."""

import asyncio
import hashlib
import logging

import google.generativeai as genai

from config import settings

logger = logging.getLogger(__name__)


def _configure_genai() -> None:
    genai.configure(api_key=settings.gemini_api_key)


def compute_combined_hash(question: str, answer: str) -> str:
    """MD5 of '{question} {answer}' truncated to 2000 chars — matches V3 engine exactly."""
    combined = f"{question} {answer}"[: settings.embedding_max_chars]
    return hashlib.md5(combined.encode("utf-8")).hexdigest()


async def embed_document(text: str) -> list[float]:
    """Embed a single document text using Gemini (retrieval_document task)."""
    _configure_genai()
    truncated = text[: settings.embedding_max_chars]
    result = await asyncio.to_thread(
        genai.embed_content,
        model=settings.embedding_model,
        content=truncated,
        task_type="retrieval_document",
    )
    return result["embedding"]


async def embed_documents_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of documents sequentially (Gemini has no native batch endpoint)."""
    embeddings: list[list[float]] = []
    for i, text in enumerate(texts):
        try:
            emb = await embed_document(text)
            embeddings.append(emb)
        except Exception as e:
            logger.error("Embedding failed for doc %d: %s", i, e)
            embeddings.append([0.0] * settings.embedding_dim)
        if (i + 1) % 100 == 0:
            logger.info("   ... embedded %d/%d", i + 1, len(texts))
    return embeddings


async def embed_query(text: str) -> list[float]:
    """Embed a user query using Gemini (retrieval_query task)."""
    _configure_genai()
    result = await asyncio.to_thread(
        genai.embed_content,
        model=settings.embedding_model,
        content=text,
        task_type="retrieval_query",
    )
    return result["embedding"]
