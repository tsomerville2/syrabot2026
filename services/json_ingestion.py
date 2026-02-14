"""Parse uploaded JSON files, diff against existing data, and embed new QA pairs."""

import json
import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import Client, QAPair, Topic
from services.embedding import compute_combined_hash, embed_documents_batch

logger = logging.getLogger(__name__)


@dataclass
class IngestionStats:
    topics_total: int = 0
    qa_pairs_total: int = 0
    qa_pairs_new: int = 0
    qa_pairs_unchanged: int = 0
    qa_pairs_removed: int = 0
    version: int = 0
    errors: list[str] = field(default_factory=list)


def _parse_json(raw: bytes) -> list[dict]:
    """Parse JSON supporting both legacy array and {tree, topics} format."""
    data = json.loads(raw)

    if isinstance(data, dict) and "topics" in data:
        return data["topics"]
    if isinstance(data, list):
        return data

    raise ValueError("Unsupported JSON format — expected a list or {topics: [...]}.")


async def ingest(db: AsyncSession, client_id: uuid.UUID, raw_json: bytes) -> IngestionStats:
    """Full ingestion pipeline: parse → diff → embed new → atomic commit."""
    stats = IngestionStats()

    # 1. Parse JSON
    topics_data = _parse_json(raw_json)
    stats.topics_total = len(topics_data)

    # 2. Bump client version
    client = await db.get(Client, client_id)
    if client is None:
        raise ValueError(f"Client {client_id} not found")
    new_version = client.active_version + 1
    client.active_version = new_version
    stats.version = new_version

    # 3. Build lookup of existing active hashes → QAPair ids
    existing_rows = (
        await db.execute(
            select(QAPair.id, QAPair.combined_hash).where(
                QAPair.client_id == client_id,
                QAPair.is_active == True,  # noqa: E712
            )
        )
    ).all()
    existing_hash_map: dict[str, uuid.UUID] = {row.combined_hash: row.id for row in existing_rows}
    seen_hashes: set[str] = set()

    # 4. Deactivate old topics for this client
    await db.execute(
        update(Topic)
        .where(Topic.client_id == client_id, Topic.is_active == True)  # noqa: E712
        .values(is_active=False)
    )

    # 5. Walk topics and build new QA pairs
    new_pairs_to_embed: list[tuple[QAPair, str]] = []  # (pair, text_to_embed)

    for topic_idx, topic_data in enumerate(topics_data):
        topic = Topic(
            client_id=client_id,
            topic_index=topic_idx,
            topic_name=topic_data.get("topic", ""),
            semantic_path=topic_data.get("semantic_path", ""),
            original_url=topic_data.get("original_url", ""),
            browser_content=topic_data.get("browser_content", ""),
            version=new_version,
            is_active=True,
        )
        db.add(topic)
        await db.flush()  # get topic.id

        for qa_idx, qa_data in enumerate(topic_data.get("qa_pairs", [])):
            question = qa_data["question"]
            answer = qa_data["answer"]
            combined_hash = compute_combined_hash(question, answer)
            seen_hashes.add(combined_hash)

            if combined_hash in existing_hash_map:
                # Unchanged — bump version on existing row, keep embedding
                old_id = existing_hash_map[combined_hash]
                await db.execute(
                    update(QAPair)
                    .where(QAPair.id == old_id)
                    .values(
                        topic_id=topic.id,
                        version=new_version,
                        is_active=True,
                        qa_index=qa_idx,
                        is_bucketed=qa_data.get("is_bucketed", False),
                        bucket_id=qa_data.get("bucket_id"),
                    )
                )
                stats.qa_pairs_unchanged += 1
            else:
                # New — need embedding
                pair = QAPair(
                    client_id=client_id,
                    topic_id=topic.id,
                    question=question,
                    answer=answer,
                    qa_index=qa_idx,
                    is_bucketed=qa_data.get("is_bucketed", False),
                    bucket_id=qa_data.get("bucket_id"),
                    combined_hash=combined_hash,
                    version=new_version,
                    is_active=True,
                )
                db.add(pair)
                combined_text = f"{question} {answer}"[:2000]
                new_pairs_to_embed.append((pair, combined_text))

            stats.qa_pairs_total += 1

    # 6. Soft-delete removed pairs (hash no longer present)
    removed_hashes = set(existing_hash_map.keys()) - seen_hashes
    if removed_hashes:
        removed_ids = [existing_hash_map[h] for h in removed_hashes]
        await db.execute(
            update(QAPair)
            .where(QAPair.id.in_(removed_ids))
            .values(is_active=False)
        )
        stats.qa_pairs_removed = len(removed_ids)

    # 7. Embed new pairs
    if new_pairs_to_embed:
        logger.info("Embedding %d new QA pairs...", len(new_pairs_to_embed))
        texts = [text for _, text in new_pairs_to_embed]
        embeddings = await embed_documents_batch(texts)

        for (pair, _), emb in zip(new_pairs_to_embed, embeddings):
            pair.embedding = emb

        stats.qa_pairs_new = len(new_pairs_to_embed)

    # 8. Atomic commit
    await db.commit()

    logger.info(
        "Ingestion complete v%d: %d topics, %d total QA (%d new, %d unchanged, %d removed)",
        stats.version,
        stats.topics_total,
        stats.qa_pairs_total,
        stats.qa_pairs_new,
        stats.qa_pairs_unchanged,
        stats.qa_pairs_removed,
    )
    return stats
