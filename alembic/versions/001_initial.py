"""Initial schema with pgvector

Revision ID: 001
Revises:
Create Date: 2025-01-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- clients ---
    op.create_table(
        "clients",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("api_key", sa.String(128), unique=True, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("active_version", sa.Integer(), server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_clients_api_key", "clients", ["api_key"])

    # --- topics ---
    op.create_table(
        "topics",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("client_id", sa.UUID(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic_index", sa.Integer(), nullable=False),
        sa.Column("topic_name", sa.String(500), nullable=False),
        sa.Column("semantic_path", sa.Text()),
        sa.Column("original_url", sa.Text()),
        sa.Column("browser_content", sa.Text()),
        sa.Column("version", sa.Integer(), server_default=sa.text("1")),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- qa_pairs ---
    op.create_table(
        "qa_pairs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("client_id", sa.UUID(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic_id", sa.UUID(), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("qa_index", sa.Integer(), nullable=False),
        sa.Column("is_bucketed", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("bucket_id", sa.String(100)),
        sa.Column("embedding", Vector(3072)),
        sa.Column("combined_hash", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1")),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_qa_pairs_client_active", "qa_pairs", ["client_id", "is_active"])
    op.create_index("ix_qa_pairs_combined_hash", "qa_pairs", ["client_id", "combined_hash"])

    # pgvector HNSW/IVFFlat indexes cap at 2000 dimensions.
    # Gemini embeddings are 3072-dim, so we skip the vector index.
    # Exact scan via <=> operator is fast for <50K rows.

    # --- conversations ---
    op.create_table(
        "conversations",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("client_id", sa.UUID(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(255), nullable=False),
        sa.Column("user_question", sa.Text(), nullable=False),
        sa.Column("bot_answer", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("matched_by", sa.String(50), server_default=sa.text("'v3_gemini_qa'")),
        sa.Column("source_topic", sa.String(500)),
        sa.Column("source_url", sa.Text()),
        sa.Column("matched_qa_id", sa.UUID(), sa.ForeignKey("qa_pairs.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_conversations_session", "conversations", ["client_id", "session_id", "created_at"])


def downgrade() -> None:
    op.drop_table("conversations")
    op.drop_table("qa_pairs")
    op.drop_table("topics")
    op.drop_table("clients")
    op.execute("DROP EXTENSION IF EXISTS vector")
