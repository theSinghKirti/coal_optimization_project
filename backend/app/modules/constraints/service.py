"""FSA / Bridge Linkage business rules."""

import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationFailedError
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
        "contract_end_date": str(record.contract_end_date) if record.contract_end_date else None,
        "is_active": record.is_active,
    }
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(record, key, value)
    if record.contract_start_date and record.contract_end_date:
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


def review_constraint(db: Session, record_id: uuid.UUID, payload: object) -> FSAConstraint:
    from app.modules.constraints.schemas import FSAConstraintReview
    assert isinstance(payload, FSAConstraintReview)

    record = repository.get(db, record_id)
    if not record:
        raise NotFoundError("Constraint not found.")

    before = {
        "status": record.status,
        "is_active": record.is_active,
        "plant_id": str(record.plant_id) if record.plant_id else None,
    }

    if payload.status == "APPROVED":
        if record.status != "PENDING_REVIEW":
            raise ValidationFailedError("Constraint must be in PENDING_REVIEW status to be approved.")

        plant_id = payload.plant_id or record.plant_id
        if not plant_id:
            raise ValidationFailedError("Plant ID must be resolved or provided to approve constraint.")
        
        if not master_data_repository.get_plant(db, plant_id):
            raise NotFoundError("Plant not found.")

        qty = record.quantity_mt if record.quantity_mt is not None else record.annual_contract_quantity_mt
        if qty is None or qty < 0:
            raise ValidationFailedError("Quantity must be present and non-negative to approve constraint.")

        if not record.document_id:
            raise ValidationFailedError("Document ID must be present to approve constraint.")

        from app.modules.constraints.models import CONSTRAINT_TYPES
        if record.constraint_type not in CONSTRAINT_TYPES:
            raise ValidationFailedError(f"Constraint type '{record.constraint_type}' is invalid.")

        record.plant_id = plant_id
        record.status = "APPROVED"
        record.is_active = True


        if payload.supplier_id:
            if not master_data_repository.get_supplier(db, payload.supplier_id):
                raise NotFoundError("Supplier not found.")
            record.supplier_id = payload.supplier_id

        if payload.coal_company_id:
            if not master_data_repository.get_coal_company(db, payload.coal_company_id):
                raise NotFoundError("Coal company not found.")
            record.coal_company_id = payload.coal_company_id

    elif payload.status == "REJECTED":
        record.status = "REJECTED"
        record.is_active = False

    db.flush()

    audit_service.record(
        db,
        entity_type="fsa_constraint",
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

