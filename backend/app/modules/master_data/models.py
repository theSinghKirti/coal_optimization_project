"""Master data: plants, plant aliases, coal companies, suppliers."""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.mixins import TimestampMixin, UUIDPKMixin
from app.core.database import Base


class Plant(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "plants"

    plant_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    plant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    aliases: Mapped[list["PlantAlias"]] = relationship(back_populates="plant", cascade="all, delete-orphan")


class PlantAlias(Base, UUIDPKMixin, TimestampMixin):
    """Alternate/inconsistent plant names seen in UPSLDC PDFs, normalized to a canonical Plant."""

    __tablename__ = "plant_aliases"
    __table_args__ = (UniqueConstraint("alias_name", name="uq_plant_alias_name"),)

    plant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("plants.id", ondelete="CASCADE"), nullable=False
    )
    alias_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    plant: Mapped["Plant"] = relationship(back_populates="aliases")


class CoalCompany(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "coal_companies"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    code: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)

    suppliers: Mapped[list["Supplier"]] = relationship(back_populates="coal_company")


class Supplier(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "suppliers"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    code: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    coal_company_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("coal_companies.id", ondelete="SET NULL"), nullable=True
    )

    coal_company: Mapped["CoalCompany | None"] = relationship(back_populates="suppliers")
