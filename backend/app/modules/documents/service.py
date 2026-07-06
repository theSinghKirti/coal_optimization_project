"""Document archive + Variable Cost ingestion business rules."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.modules.audit import service as audit_service
from app.modules.documents import repository
from app.modules.documents.models import DOCUMENT_TYPES, Document, VariableCost
from app.modules.documents.storage import compute_sha256, save_file
from app.modules.documents.variable_cost_parser import parse_variable_cost_pdf
from app.modules.master_data.models import Plant, PlantAlias


def _build_known_plant_tokens(db: Session) -> dict[str, str]:
    """Builds {alias/name -> canonical display name} from master data."""
    tokens: dict[str, str] = {}
    plants = list(db.execute(select(Plant)).scalars().all())
    for plant in plants:
        tokens[plant.plant_name] = plant.plant_name
        tokens[plant.plant_code] = plant.plant_name
    aliases = list(db.execute(select(PlantAlias)).scalars().all())
    alias_by_plant = {p.id: p for p in plants}
    for alias in aliases:
        plant = alias_by_plant.get(alias.plant_id)
        if plant:
            tokens[alias.alias_name] = plant.plant_name
    return tokens


def _resolve_plant_id_for_token(db: Session, matched_display_name: str) -> uuid.UUID | None:
    from app.modules.master_data.service import resolve_plant_by_name
    plant = resolve_plant_by_name(db, matched_display_name)
    return plant.id if plant else None


def upload_document(
    db: Session,
    *,
    content: bytes,
    original_filename: str,
    document_type: str,
    plant_id: uuid.UUID | None,
    notes: str | None,
) -> Document:
    if document_type not in DOCUMENT_TYPES:
        raise ValidationFailedError(f"Unknown document_type '{document_type}'.")

    file_hash = compute_sha256(content)
    if repository.get_document_by_hash(db, file_hash):
        raise ConflictError("A document with identical content (SHA-256 hash) already exists.")

    storage_path = save_file(content, original_filename, subfolder=document_type.lower())

    document = repository.create_document(
        db,
        document_type=document_type,
        original_filename=original_filename,
        storage_path=storage_path,
        sha256_hash=file_hash,
        plant_id=plant_id,
        needs_review=False,
        review_status="approved",
        notes=notes,
    )

    audit_service.record(
        db,
        entity_type="document",
        entity_id=document.id,
        action="create",
        after={
            "document_type": document_type,
            "original_filename": original_filename,
            "sha256_hash": file_hash,
        },
    )
    return document


def upload_and_parse_variable_cost_pdf(
    db: Session, *, content: bytes, original_filename: str
) -> tuple[Document, list[VariableCost], list[str]]:
    """Stores the PDF first (per rule: 'PDF must be stored before parsing'), then parses it."""
    file_hash = compute_sha256(content)
    if repository.get_document_by_hash(db, file_hash):
        raise ConflictError("A document with identical content (SHA-256 hash) already exists.")

    storage_path = save_file(content, original_filename, subfolder="variable_cost_pdf")

    document = repository.create_document(
        db,
        document_type="VARIABLE_COST_PDF",
        original_filename=original_filename,
        storage_path=storage_path,
        sha256_hash=file_hash,
        plant_id=None,
        needs_review=False,
        review_status="approved",
        notes=None,
    )

    known_tokens = _build_known_plant_tokens(db)
    parse_result = parse_variable_cost_pdf(content, known_tokens)

    if not parse_result.text_extracted:
        document.needs_review = True
        document.review_status = "needs_review"
        document.notes = "; ".join(parse_result.notes) or "Text extraction failed."
        db.flush()
        audit_service.record(
            db,
            entity_type="document",
            entity_id=document.id,
            action="create",
            after={"document_type": "VARIABLE_COST_PDF", "needs_review": True},
            note="Marked needs_review: text extraction failed.",
        )
        return document, [], parse_result.notes

    created_rows: list[VariableCost] = []
    for row in parse_result.rows:
        plant_id = _resolve_plant_id_for_token(db, row.matched_plant_token) if row.confident else None
        needs_review = not row.confident or plant_id is None

        vc = repository.create_variable_cost(
            db,
            plant_id=plant_id,
            document_id=document.id,
            source_plant_name=row.source_plant_name,
            effective_date=row.effective_date,
            variable_cost_per_unit=row.variable_cost_per_unit or 0,
            unit="Rs/kWh",
            needs_review=needs_review,
        )
        created_rows.append(vc)

    if any(r.needs_review for r in created_rows):
        document.needs_review = True
        document.review_status = "needs_review"

    db.flush()
    audit_service.record(
        db,
        entity_type="document",
        entity_id=document.id,
        action="create",
        after={
            "document_type": "VARIABLE_COST_PDF",
            "rows_parsed": len(created_rows),
            "rows_needing_review": sum(1 for r in created_rows if r.needs_review),
        },
    )
    return document, created_rows, parse_result.notes


def review_variable_cost(
    db: Session, vc_id: uuid.UUID, *, plant_id: uuid.UUID, needs_review: bool
) -> VariableCost:
    vc = repository.get_variable_cost(db, vc_id)
    if not vc:
        raise NotFoundError("Variable Cost record not found.")
    before = {
        "plant_id": str(vc.plant_id) if vc.plant_id else None,
        "needs_review": vc.needs_review,
    }
    vc.plant_id = plant_id
    vc.needs_review = needs_review
    db.flush()
    audit_service.record(
        db,
        entity_type="variable_cost",
        entity_id=vc.id,
        action="update",
        before=before,
        after={"plant_id": str(plant_id), "needs_review": needs_review},
        note="Manual review",
    )
    return vc


def get_document_or_404(db: Session, document_id: uuid.UUID) -> Document:
    document = repository.get_document(db, document_id)
    if not document:
        raise NotFoundError("Document not found.")
    return document


def list_documents(db: Session, **filters):
    return repository.list_documents(db, **filters)


def list_variable_costs(db: Session, **filters):
    return repository.list_variable_costs(db, **filters)


def latest_variable_costs(db: Session) -> list[VariableCost]:
    return repository.latest_variable_cost_per_plant(db)
