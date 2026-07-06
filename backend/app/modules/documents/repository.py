import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.documents.models import Document, VariableCost


def create_document(db: Session, **kwargs) -> Document:
    document = Document(**kwargs)
    db.add(document)
    db.flush()
    return document


def get_document(db: Session, document_id: uuid.UUID) -> Document | None:
    return db.get(Document, document_id)


def get_document_by_hash(db: Session, sha256_hash: str) -> Document | None:
    return db.execute(select(Document).where(Document.sha256_hash == sha256_hash)).scalar_one_or_none()


def list_documents(
    db: Session,
    *,
    document_type: str | None = None,
    needs_review: bool | None = None,
    limit: int = 50,
    offset: int = 0,
):
    stmt = select(Document)
    count_stmt = select(func.count()).select_from(Document)
    if document_type:
        stmt = stmt.where(Document.document_type == document_type)
        count_stmt = count_stmt.where(Document.document_type == document_type)
    if needs_review is not None:
        stmt = stmt.where(Document.needs_review == needs_review)
        count_stmt = count_stmt.where(Document.needs_review == needs_review)
    total = db.execute(count_stmt).scalar_one()
    stmt = stmt.order_by(Document.created_at.desc()).offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all()), total


def create_variable_cost(db: Session, **kwargs) -> VariableCost:
    vc = VariableCost(**kwargs)
    db.add(vc)
    db.flush()
    return vc


def get_variable_cost(db: Session, vc_id: uuid.UUID) -> VariableCost | None:
    return db.get(VariableCost, vc_id)


def list_variable_costs(
    db: Session,
    *,
    plant_id: uuid.UUID | None = None,
    needs_review: bool | None = None,
    limit: int = 50,
    offset: int = 0,
):
    stmt = select(VariableCost)
    count_stmt = select(func.count()).select_from(VariableCost)
    if plant_id:
        stmt = stmt.where(VariableCost.plant_id == plant_id)
        count_stmt = count_stmt.where(VariableCost.plant_id == plant_id)
    if needs_review is not None:
        stmt = stmt.where(VariableCost.needs_review == needs_review)
        count_stmt = count_stmt.where(VariableCost.needs_review == needs_review)
    total = db.execute(count_stmt).scalar_one()
    stmt = stmt.order_by(VariableCost.created_at.desc()).offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all()), total


def latest_variable_cost_per_plant(db: Session) -> list[VariableCost]:
    """Latest (by created_at) Variable Cost row per plant, ignoring rows needing review."""
    from app.modules.master_data.models import Plant

    results = []
    plants = list(db.execute(select(Plant)).scalars().all())
    for plant in plants:
        latest = db.execute(
            select(VariableCost)
            .where(VariableCost.plant_id == plant.id, VariableCost.needs_review.is_(False))
            .order_by(VariableCost.effective_date.desc().nullslast(), VariableCost.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if latest:
            results.append(latest)
    return results
