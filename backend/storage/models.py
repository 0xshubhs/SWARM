"""SQLAlchemy 2 ORM models. Mirrors the alembic 001_initial migration."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    seller: Mapped[str] = mapped_column(String(44), index=True)
    title: Mapped[str] = mapped_column(String(128))
    model_id: Mapped[str] = mapped_column(String(64), index=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String))
    price_usdc: Mapped[int] = mapped_column(BigInteger)
    sandbox_price_usdc: Mapped[int] = mapped_column(BigInteger)
    arweave_tx: Mapped[str] = mapped_column(String(43))
    content_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    quant_seed: Mapped[int] = mapped_column(BigInteger)
    bits_per_channel: Mapped[int] = mapped_column(SmallInteger)
    seq_len: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    purchases: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    on_chain_slot: Mapped[int] = mapped_column(BigInteger)


class Purchase(Base):
    __tablename__ = "purchases"

    license_pda: Mapped[str] = mapped_column(String(64), primary_key=True)
    buyer: Mapped[str] = mapped_column(String(44), index=True)
    listing_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("listings.id"), index=True
    )
    price_paid_usdc: Mapped[int] = mapped_column(BigInteger)
    tx_signature: Mapped[str] = mapped_column(String(88))
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SandboxQuery(Base):
    __tablename__ = "sandbox_queries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    buyer: Mapped[str] = mapped_column(String(44), index=True)
    listing_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("listings.id"), index=True
    )
    query: Mapped[str] = mapped_column(Text)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    payment_tx: Mapped[str | None] = mapped_column(String(88), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(44), index=True)
    decision_type: Mapped[str] = mapped_column(String(32), index=True)
    context_hash: Mapped[bytes] = mapped_column(LargeBinary(32))
    arweave_tx: Mapped[str] = mapped_column(String(43))
    decision_data: Mapped[bytes] = mapped_column(LargeBinary)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    on_chain_slot: Mapped[int] = mapped_column(BigInteger)


class CompressJob(Base):
    __tablename__ = "compress_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    seller: Mapped[str] = mapped_column(String(44), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)  # queued|running|done|failed
    input_size_bytes: Mapped[int] = mapped_column(BigInteger)
    output_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    content_hash: Mapped[bytes | None] = mapped_column(LargeBinary(32), nullable=True)
    arweave_tx: Mapped[str | None] = mapped_column(String(43), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
