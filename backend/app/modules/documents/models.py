"""Static document archive + parsed Variable Cost history.

Documents cover FSA, Bridge Linkage, Landed Cost, IPP Rules, Government Orders,
and UPSLDC Variable Cost PDFs. Variable Cost rows are parsed deterministically
from uploaded PDFs and are always append-only (never overwritten).
"""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.mixins import TimestampMixin, UUIDPKMixin
from app.core.database import Base

DOCUMENT_TYPES = (
    "FSA",
    "BRIDGE_LINKAGE",
    "FSA_BRIDGE_LINKAGE_DOCUMENT",
    "LANDED_COST_DOCUMENT",
    "LANDED_COST",
    "IPP_RULES",
    "GOVERNMENT_ORDER",
    "VARIABLE_COST_PDF",
    "OTHER",
)




class Document(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "documents"

    document_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    plant_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("plants.id", ondelete="SET NULL"), nullable=True
    )

    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="approved")
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    variable_costs: Mapped[list["VariableCost"]] = relationship(back_populates="document")


class VariableCost(Base, UUIDPKMixin, TimestampMixin):
    """Historical, append-only plant-wise Variable Cost extracted from UPSLDC PDFs."""

    __tablename__ = "variable_costs"

    plant_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )

    source_plant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    variable_cost_per_unit: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="Rs/kWh")

    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    document: Mapped["Document"] = relationship(back_populates="variable_costs")
    plant = relationship("Plant")
