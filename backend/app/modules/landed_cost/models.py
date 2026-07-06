"""Landed coal cost records: the actual delivered cost used for optimization."""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.mixins import TimestampMixin, UUIDPKMixin
from app.core.database import Base


class LandedCost(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "landed_costs"

    plant_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plants.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )

    basic_cost: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    freight: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    taxes: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    other_cost: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_landed_cost: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)

    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Ingestion / draft review fields
    raw_source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    weighted_avg_gcv_kcal_per_kg: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    cost_basis: Mapped[str] = mapped_column(String(64), default="CERTIFIED_WEIGHTED_AVERAGE", nullable=False)
    extraction_confidence: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    parser_notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="APPROVED", nullable=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


    plant = relationship("Plant")
    supplier = relationship("Supplier")


