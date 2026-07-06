"""Business rules for master data: uniqueness checks, alias normalization."""

import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.audit import service as audit_service
from app.modules.master_data import repository
from app.modules.master_data.models import CoalCompany, Plant, PlantAlias, Supplier
from app.modules.master_data.schemas import (
    CoalCompanyCreate,
    PlantAliasCreate,
    PlantCreate,
    PlantUpdate,
    SupplierCreate,
)

AMBIGUOUS_GENERIC_NAMES = {"anpara", "obra", "parichha"}

def normalize_name(name: str) -> str:
    """Normalize names by lowercasing and stripping all non-alphanumeric characters."""
    val = name.lower()
    return re.sub(r"[^a-z0-9]", "", val)


# ---- Plant ----
def create_plant(db: Session, payload: PlantCreate) -> Plant:
    if repository.get_plant_by_code(db, payload.plant_code):
        raise ConflictError(f"Plant code '{payload.plant_code}' already exists.")

    norm_code = normalize_name(payload.plant_code)
    norm_name = normalize_name(payload.plant_name)

    if norm_code in AMBIGUOUS_GENERIC_NAMES or norm_name in AMBIGUOUS_GENERIC_NAMES:
        raise ConflictError("Cannot create plant with an ambiguous generic station name.")

    # Check for conflicts with existing plants/aliases
    for p in db.execute(select(Plant)).scalars().all():
        if normalize_name(p.plant_code) == norm_code or normalize_name(p.plant_name) == norm_code:
            raise ConflictError(f"Plant code conflicts with existing plant '{p.plant_code}'.")
        if normalize_name(p.plant_code) == norm_name or normalize_name(p.plant_name) == norm_name:
            raise ConflictError(f"Plant name conflicts with existing plant '{p.plant_code}'.")

    for a in db.execute(select(PlantAlias)).scalars().all():
        if normalize_name(a.alias_name) == norm_code:
            raise ConflictError(f"Plant code conflicts with alias for plant '{a.plant.plant_code}'.")
        if normalize_name(a.alias_name) == norm_name:
            raise ConflictError(f"Plant name conflicts with alias for plant '{a.plant.plant_code}'.")

    plant = repository.create_plant(db, **payload.model_dump())
    audit_service.record(
        db,
        entity_type="plant",
        entity_id=plant.id,
        action="create",
        after=payload.model_dump(mode="json"),
    )
    return plant


def update_plant(db: Session, plant_id: uuid.UUID, payload: PlantUpdate) -> Plant:
    plant = repository.get_plant(db, plant_id)
    if not plant:
        raise NotFoundError("Plant not found.")
    before = {"plant_name": plant.plant_name, "is_active": plant.is_active}
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(plant, key, value)
    db.flush()
    audit_service.record(
        db, entity_type="plant", entity_id=plant.id, action="update", before=before, after=data
    )
    return plant


def get_plant_or_404(db: Session, plant_id: uuid.UUID) -> Plant:
    plant = repository.get_plant(db, plant_id)
    if not plant:
        raise NotFoundError("Plant not found.")
    return plant


def list_plants(db: Session, *, is_active: bool | None, limit: int, offset: int):
    return repository.list_plants(db, is_active=is_active, limit=limit, offset=offset)


# ---- Plant Alias ----
def create_alias(db: Session, payload: PlantAliasCreate) -> PlantAlias:
    if not repository.get_plant(db, payload.plant_id):
        raise NotFoundError("Plant not found for alias.")
    if repository.get_alias_by_name(db, payload.alias_name):
        raise ConflictError(f"Alias '{payload.alias_name}' already mapped to a plant.")

    norm_name = normalize_name(payload.alias_name)
    if norm_name in AMBIGUOUS_GENERIC_NAMES:
        raise ConflictError(f"Alias '{payload.alias_name}' is an unsafe generic station name.")

    # Check duplicate normalized aliases pointing to different plant IDs
    for p in db.execute(select(Plant)).scalars().all():
        if p.id != payload.plant_id:
            if normalize_name(p.plant_code) == norm_name or normalize_name(p.plant_name) == norm_name:
                raise ConflictError(f"Alias '{payload.alias_name}' conflicts with plant '{p.plant_code}'.")

    for a in db.execute(select(PlantAlias)).scalars().all():
        if a.plant_id != payload.plant_id:
            if normalize_name(a.alias_name) == norm_name:
                raise ConflictError(
                    f"Alias '{payload.alias_name}' conflicts with existing alias for "
                    f"plant '{a.plant.plant_code}'."
                )

    alias = repository.create_alias(db, **payload.model_dump())
    audit_service.record(
        db,
        entity_type="plant_alias",
        entity_id=alias.id,
        action="create",
        after=payload.model_dump(mode="json"),
    )
    return alias


def list_aliases(db: Session, *, plant_id: uuid.UUID | None) -> list[PlantAlias]:
    return repository.list_aliases(db, plant_id=plant_id)


def resolve_plant_by_name(db: Session, raw_name: str) -> Plant | None:
    """Resolve a raw plant name (from a PDF or form) to a canonical Plant.

    Tries an exact plant_code/plant_name match first, then falls back to
    the plant_aliases table for known name variants.
    """
    normalized = raw_name.strip()
    plant = repository.get_plant_by_code(db, normalized)
    if plant:
        return plant

    from sqlalchemy import select

    plant = db.execute(select(Plant).where(Plant.plant_name.ilike(normalized))).scalar_one_or_none()
    if plant:
        return plant

    alias = repository.get_alias_by_name(db, normalized)
    if alias:
        return alias.plant

    return None


# ---- Coal Company ----
def create_coal_company(db: Session, payload: CoalCompanyCreate) -> CoalCompany:
    company = repository.create_coal_company(db, **payload.model_dump())
    audit_service.record(
        db,
        entity_type="coal_company",
        entity_id=company.id,
        action="create",
        after=payload.model_dump(mode="json"),
    )
    return company


def list_coal_companies(db: Session, *, limit: int, offset: int):
    return repository.list_coal_companies(db, limit=limit, offset=offset)


# ---- Supplier ----
def create_supplier(db: Session, payload: SupplierCreate) -> Supplier:
    if payload.coal_company_id and not repository.get_coal_company(db, payload.coal_company_id):
        raise NotFoundError("Coal company not found for supplier.")
    supplier = repository.create_supplier(db, **payload.model_dump())
    audit_service.record(
        db,
        entity_type="supplier",
        entity_id=supplier.id,
        action="create",
        after=payload.model_dump(mode="json"),
    )
    return supplier


def list_suppliers(db: Session, *, limit: int, offset: int):
    return repository.list_suppliers(db, limit=limit, offset=offset)
