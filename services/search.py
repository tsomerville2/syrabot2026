"""pgvector cosine similarity search."""

import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.embedding import embed_query

logger = logging.getLogger(__name__)


async def search(
    db: AsyncSession,
    client_id: uuid.UUID,
    question: str,
    top_k: int = 1,
) -> list[dict]:
    """Embed user question and find the closest QA pair via pgvector cosine distance."""
    query_embedding = await embed_query(question)

    sql = text("""
        SELECT
            q.id,
            q.topic_id,
            q.question,
            q.answer,
            t.topic_name AS source_topic,
            t.original_url AS source_url,
            1 - (q.embedding <=> :query_vec) AS similarity
        FROM qa_pairs q
        JOIN topics t ON q.topic_id = t.id
        WHERE q.client_id = :client_id
          AND q.is_active = TRUE
          AND q.embedding IS NOT NULL
        ORDER BY q.embedding <=> :query_vec
        LIMIT :top_k
    """)

    result = await db.execute(
        sql,
        {
            "client_id": str(client_id),
            "query_vec": str(query_embedding),
            "top_k": top_k,
        },
    )
    rows = result.mappings().all()

    return [
        {
            "qa_id": row["id"],
            "topic_id": row["topic_id"],
            "question": row["question"],
            "answer": row["answer"],
            "source_topic": row["source_topic"],
            "source_url": row["source_url"],
            "similarity": float(row["similarity"]),
        }
        for row in rows
    ]
