"""FSA / Bridge Linkage business rules."""

import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.modules.audit import service as audit_service
from app.modules.constraints import repository
from app.modules.constraints.models import FSAConstraint
from app.modules.constraints.schemas import FSAConstraintCreate, FSAConstraintUpdate
from app.modules.master_data import repository as master_data_repository


def create_constraint(db: Session, payload: FSAConstraintCreate) -> FSAConstraint:
    if not master_data_repository.get_plant(db, payload.plant_id):
        raise NotFoundError("Plant not found for constraint.")
    if payload.supplier_id and not master_data_repository.get_supplier(db, payload.supplier_id):
        raise NotFoundError("Supplier not found for constraint.")
    if payload.coal_company_id and not master_data_repository.get_coal_company(db, payload.coal_company_id):
        raise NotFoundError("Coal company not found for constraint.")

    record = repository.create(db, **payload.model_dump())
    audit_service.record(
        db,
        entity_type="fsa_constraint",
        entity_id=record.id,
        action="create",
        after=payload.model_dump(mode="json"),
    )
    return record


def update_constraint(db: Session, record_id: uuid.UUID, payload: FSAConstraintUpdate) -> FSAConstraint:
    record = repository.get(db, record_id)
    if not record:
        raise NotFoundError("Constraint not found.")
    before = {
        "monthly_cap_mt": float(record.monthly_cap_mt) if record.monthly_cap_mt else None,
        "contract_end_date": str(record.contract_end_date),
        "is_active": record.is_active,
    }
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(record, key, value)
    if record.contract_end_date < record.contract_start_date:
        raise ValueError("contract_end_date cannot be earlier than contract_start_date.")
    db.flush()
    audit_service.record(
        db,
        entity_type="fsa_constraint",
        entity_id=record.id,
        action="update",
        before=before,
        after=data,
    )
    return record


def get_or_404(db: Session, record_id: uuid.UUID) -> FSAConstraint:
    record = repository.get(db, record_id)
    if not record:
        raise NotFoundError("Constraint not found.")
    return record


def list_constraints(db: Session, **filters):
    return repository.list_records(db, **filters)
