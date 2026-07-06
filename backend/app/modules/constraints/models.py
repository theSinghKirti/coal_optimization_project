"""FSA and Bridge Linkage constraints: contractual coal allocation limits."""

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.mixins import TimestampMixin, UUIDPKMixin
from app.core.database import Base

CONSTRAINT_TYPES = ("FSA", "BRIDGE_LINKAGE")


class FSAConstraint(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "fsa_constraints"

    constraint_type: Mapped[str] = mapped_column(String(32), nullable=False, default="FSA")

    plant_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plants.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True
    )
    coal_company_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("coal_companies.id", ondelete="SET NULL"), nullable=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )

    annual_contract_quantity_mt: Mapped[float | None] = mapped_column(Numeric(16, 3), nullable=True)
    monthly_cap_mt: Mapped[float | None] = mapped_column(Numeric(16, 3), nullable=True)

    contract_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Added columns for draft PDF extraction
    fiscal_year: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    coal_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity_lac_mt: Mapped[float | None] = mapped_column(Numeric(16, 4), nullable=True)
    quantity_mt: Mapped[float | None] = mapped_column(Numeric(16, 3), nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    remarks: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    extraction_confidence: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    parser_notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING_REVIEW", nullable=False)

    plant = relationship("Plant")
    supplier = relationship("Supplier")
    coal_company_rel = relationship("CoalCompany")


