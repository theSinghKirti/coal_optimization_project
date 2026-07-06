"""Optimization run snapshots, allocation results, and recommendations tables."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.mixins import UUIDPKMixin
from app.core.database import Base


class OptimizationRun(Base, UUIDPKMixin):
    __tablename__ = "optimization_runs"

    run_timestamp: Mapped[datetime] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # completed|incomplete_data|failed
    triggered_by: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    solver_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    total_estimated_cost: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    input_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    allocations: Mapped[list["AllocationResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class AllocationResult(Base, UUIDPKMixin):
    __tablename__ = "allocation_results"

    run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("optimization_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    plant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("plants.id", ondelete="RESTRICT"), nullable=False
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True
    )

    allocation_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # fsa|bridge_linkage|market_topup
    quantity_mt: Mapped[float] = mapped_column(Numeric(16, 3), nullable=False)
    unit_cost: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    estimated_cost: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    acq_utilization_pct: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    run: Mapped["OptimizationRun"] = relationship(back_populates="allocations")
    plant = relationship("Plant")
    supplier = relationship("Supplier")
