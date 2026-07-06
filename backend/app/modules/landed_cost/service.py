"""Landed cost business rules.

Total Landed Cost = Basic Cost + Freight + Taxes + Other Cost
Never invented: if a plant has no active landed cost, optimization must treat
that as missing data (never fabricate a number here).
"""

import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.modules.audit import service as audit_service
from app.modules.landed_cost import repository
from app.modules.landed_cost.models import LandedCost
from app.modules.landed_cost.schemas import LandedCostCreate, LandedCostUpdate
from app.modules.master_data import repository as master_data_repository


def create_landed_cost(db: Session, payload: LandedCostCreate) -> LandedCost:
    if payload.plant_id and not master_data_repository.get_plant(db, payload.plant_id):
        raise NotFoundError("Plant not found for landed cost record.")
    if payload.supplier_id and not master_data_repository.get_supplier(db, payload.supplier_id):
        raise NotFoundError("Supplier not found for landed cost record.")

    if payload.basic_cost is not None and payload.freight is not None and payload.taxes is not None:
        total = payload.basic_cost + payload.freight + payload.taxes + payload.other_cost
    else:
        total = payload.total_landed_cost

    data = payload.model_dump()
    data["total_landed_cost"] = total
    record = repository.create(db, **data)


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


def latest_landed_costs(db: Session) -> list[LandedCost]:
    return repository.latest_active_records(db)


def review_landed_cost(db: Session, record_id: uuid.UUID, payload: object) -> LandedCost:
    from app.modules.landed_cost.schemas import LandedCostReview
    assert isinstance(payload, LandedCostReview)

    record = repository.get(db, record_id)
    if not record:
        raise NotFoundError("Landed cost record not found.")

    before = {
        "status": record.status,
        "is_active": record.is_active,
        "plant_id": str(record.plant_id) if record.plant_id else None,
    }

    if payload.status == "APPROVED":
        if record.status != "PENDING_REVIEW":
            raise ValidationFailedError("Landed cost record must be in PENDING_REVIEW status to be approved.")

        plant_id = payload.plant_id or record.plant_id
        if not plant_id:
            raise ValidationFailedError(
                "Plant ID must be resolved or provided to approve landed cost record."
            )

        if not master_data_repository.get_plant(db, plant_id):
            raise NotFoundError("Plant not found.")

        if record.total_landed_cost is None or record.total_landed_cost <= 0:
            raise ValidationFailedError("Total landed cost must be positive to approve.")

        if not record.effective_from:
            raise ValidationFailedError("Effective from date must be present to approve.")
        if record.effective_to and record.effective_to < record.effective_from:
            raise ValidationFailedError("effective_to cannot be earlier than effective_from.")

        if not record.document_id:
            raise ValidationFailedError("Document ID must be present to approve.")


        record.plant_id = plant_id
        record.status = "APPROVED"
        record.is_active = True

        if payload.supplier_id:
            if not master_data_repository.get_supplier(db, payload.supplier_id):
                raise NotFoundError("Supplier not found.")
            record.supplier_id = payload.supplier_id

    elif payload.status == "REJECTED":
        record.status = "REJECTED"
        record.is_active = False

    db.flush()

    audit_service.record(
        db,
        entity_type="landed_cost",
        entity_id=record.id,
        action="review",
        before=before,
        after={
            "status": record.status,
            "is_active": record.is_active,
            "plant_id": str(record.plant_id) if record.plant_id else None,
        },
    )
    return record

