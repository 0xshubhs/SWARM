"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-10
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "listings",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("seller", sa.String(44), nullable=False, index=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("model_id", sa.String(64), nullable=False, index=True),
        sa.Column("tags", sa.ARRAY(sa.String), nullable=False),
        sa.Column("price_usdc", sa.BigInteger, nullable=False),
        sa.Column("sandbox_price_usdc", sa.BigInteger, nullable=False),
        sa.Column("arweave_tx", sa.String(43), nullable=False),
        sa.Column("content_hash", sa.LargeBinary(32), nullable=False, unique=True),
        sa.Column("quant_seed", sa.BigInteger, nullable=False),
        sa.Column("bits_per_channel", sa.SmallInteger, nullable=False),
        sa.Column("seq_len", sa.Integer, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true(), index=True),
        sa.Column("purchases", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("on_chain_slot", sa.BigInteger, nullable=False),
    )
    op.create_index(
        "idx_listings_active_created",
        "listings",
        ["active", "created_at"],
    )

    op.create_table(
        "purchases",
        sa.Column("license_pda", sa.String(64), primary_key=True),
        sa.Column("buyer", sa.String(44), nullable=False, index=True),
        sa.Column(
            "listing_id",
            sa.String(64),
            sa.ForeignKey("listings.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("price_paid_usdc", sa.BigInteger, nullable=False),
        sa.Column("tx_signature", sa.String(88), nullable=False),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "sandbox_queries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("buyer", sa.String(44), nullable=False, index=True),
        sa.Column(
            "listing_id",
            sa.String(64),
            sa.ForeignKey("listings.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("response", sa.Text),
        sa.Column("quality_score", sa.Float),
        sa.Column("payment_tx", sa.String(88)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "decisions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("agent_id", sa.String(44), nullable=False, index=True),
        sa.Column("decision_type", sa.String(32), nullable=False, index=True),
        sa.Column("context_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("arweave_tx", sa.String(43), nullable=False),
        sa.Column("decision_data", sa.LargeBinary, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("on_chain_slot", sa.BigInteger, nullable=False),
    )

    op.create_table(
        "compress_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("seller", sa.String(44), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("input_size_bytes", sa.BigInteger, nullable=False),
        sa.Column("output_size_bytes", sa.BigInteger),
        sa.Column("content_hash", sa.LargeBinary(32)),
        sa.Column("arweave_tx", sa.String(43)),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("compress_jobs")
    op.drop_table("decisions")
    op.drop_table("sandbox_queries")
    op.drop_table("purchases")
    op.drop_index("idx_listings_active_created", table_name="listings")
    op.drop_table("listings")
