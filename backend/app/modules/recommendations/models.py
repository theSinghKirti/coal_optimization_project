"""Recommendations produced by optimization runs and stock-condition checks."""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.mixins import TimestampMixin, UUIDPKMixin
from app.core.database import Base


class Recommendation(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "recommendations"

    run_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("optimization_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    plant_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("plants.id", ondelete="SET NULL"), nullable=True
    )

    recommendation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)  # info|warning|critical
    message: Mapped[str] = mapped_column(String(1000), nullable=False)

    plant = relationship("Plant")
