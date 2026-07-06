"""Daily coal stock entry with reconciliation status."""

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.mixins import TimestampMixin, UUIDPKMixin
from app.core.database import Base


class DailyStock(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "daily_stock"
    __table_args__ = (UniqueConstraint("plant_id", "report_date", name="uq_daily_stock_plant_date"),)

    plant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("plants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    opening_stock_mt: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    receipt_mt: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    consumption_mt: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    closing_stock_mt: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)

    expected_closing_stock_mt: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    reconciliation_difference_mt: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)

    # "ok" or "warning"
    validation_status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    remarks: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    plant = relationship("Plant")
