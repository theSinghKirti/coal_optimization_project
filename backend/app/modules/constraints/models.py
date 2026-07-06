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

    plant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plants.id", ondelete="RESTRICT"),
        nullable=False,
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

    annual_contract_quantity_mt: Mapped[float] = mapped_column(Numeric(16, 3), nullable=False)
    monthly_cap_mt: Mapped[float | None] = mapped_column(Numeric(16, 3), nullable=True)

    contract_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    contract_end_date: Mapped[date] = mapped_column(Date, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    plant = relationship("Plant")
    supplier = relationship("Supplier")
    coal_company = relationship("CoalCompany")
