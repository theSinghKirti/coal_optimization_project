"""Audit log ORM model: an append-only trace of create/update/delete/optimize actions."""

import uuid

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.common.mixins import TimestampMixin, UUIDPKMixin
from app.core.database import Base


class AuditLog(Base, UUIDPKMixin):
    __tablename__ = "audit_logs"

    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)  # create/update/delete/optimize
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at = TimestampMixin.created_at
