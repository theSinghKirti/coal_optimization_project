"""Landed coal cost records: the actual delivered cost used for optimization."""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.mixins import TimestampMixin, UUIDPKMixin
from app.core.database import Base


class LandedCost(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "landed_costs"

    plant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )

    basic_cost: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    freight: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    taxes: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    other_cost: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_landed_cost: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)

    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    plant = relationship("Plant")
    supplier = relationship("Supplier")
