"""Landed cost business rules.

Total Landed Cost = Basic Cost + Freight + Taxes + Other Cost
Never invented: if a plant has no active landed cost, optimization must treat
that as missing data (never fabricate a number here).
"""

import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.modules.audit import service as audit_service
from app.modules.landed_cost import repository
from app.modules.landed_cost.models import LandedCost
from app.modules.landed_cost.schemas import LandedCostCreate, LandedCostUpdate
from app.modules.master_data import repository as master_data_repository


def create_landed_cost(db: Session, payload: LandedCostCreate) -> LandedCost:
    if not master_data_repository.get_plant(db, payload.plant_id):
        raise NotFoundError("Plant not found for landed cost record.")
    if payload.supplier_id and not master_data_repository.get_supplier(db, payload.supplier_id):
        raise NotFoundError("Supplier not found for landed cost record.")

    total = payload.basic_cost + payload.freight + payload.taxes + payload.other_cost
    data = payload.model_dump()
    record = repository.create(db, **data, total_landed_cost=total)

    audit_service.record(
        db,
        entity_type="landed_cost",
        entity_id=record.id,
        action="create",
        after={**payload.model_dump(mode="json"), "total_landed_cost": total},
    )
    return record


def update_landed_cost(db: Session, record_id: uuid.UUID, payload: LandedCostUpdate) -> LandedCost:
    record = repository.get(db, record_id)
    if not record:
        raise NotFoundError("Landed cost record not found.")
    before = {
        "effective_to": str(record.effective_to) if record.effective_to else None,
        "is_active": record.is_active,
    }
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(record, key, value)
    db.flush()
    audit_service.record(
        db,
        entity_type="landed_cost",
        entity_id=record.id,
        action="update",
        before=before,
        after=data,
    )
    return record


def get_or_404(db: Session, record_id: uuid.UUID) -> LandedCost:
    record = repository.get(db, record_id)
    if not record:
        raise NotFoundError("Landed cost record not found.")
    return record


def list_landed_costs(db: Session, **filters):
    return repository.list_records(db, **filters)
