"""Document archive + Variable Cost ingestion business rules."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.modules.audit import service as audit_service
from app.modules.constraints import repository as constraints_repository
from app.modules.constraints.models import FSAConstraint
from app.modules.documents import repository
from app.modules.documents.fsa_bridge_parser import parse_fsa_bridge_pdf
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


def extract_fsa_bridge_document(db: Session, document_id: uuid.UUID) -> tuple[list[object], list[str]]:


    document = get_document_or_404(db, document_id)
    if document.document_type != "FSA_BRIDGE_LINKAGE_DOCUMENT":
        raise ValidationFailedError(
            f"Extraction is only supported for document type 'FSA_BRIDGE_LINKAGE_DOCUMENT', "
            f"but got '{document.document_type}'."
        )

    try:
        with open(document.storage_path, "rb") as f:
            pdf_bytes = f.read()
    except Exception as e:
        raise ValidationFailedError(f"Failed to read file from storage: {e}") from e



    # Parse using new parser
    fiscal_year, extracted_rows, notes = parse_fsa_bridge_pdf(pdf_bytes)

    # Clear previous extraction results if any to support idempotent re-extraction
    db.execute(delete(FSAConstraint).where(FSAConstraint.document_id == document_id))
    db.flush()

    if not extracted_rows:
        document.needs_review = True
        document.review_status = "needs_review"
        document.notes = "; ".join(notes) or "No constraint rows could be parsed."
        db.flush()
        return [], notes

    created_records = []
    any_needs_review = False

    for row in extracted_rows:
        # Resolve plant using exact name/alias matching
        from app.modules.master_data.service import resolve_plant_by_name
        plant = resolve_plant_by_name(db, row.raw_source_name)
        plant_id = plant.id if plant else None

        # Resolve coal company using exact name/code matching
        coal_company_id = None
        if row.coal_company:
            from app.modules.master_data.models import CoalCompany
            cc = db.execute(select(CoalCompany).where(
                (CoalCompany.code == row.coal_company) | (CoalCompany.name == row.coal_company)
            )).scalars().first()
            if cc:
                coal_company_id = cc.id

        # Determine confidence and notes
        confidence = row.extraction_confidence
        notes_list = []
        if not plant_id:
            any_needs_review = True
            confidence = 0.0
            notes_list.append(f"Unresolved or ambiguous plant name: '{row.raw_source_name}'")

        parser_note = "; ".join(notes_list) if notes_list else None

        record = constraints_repository.create(
            db,
            constraint_type=row.constraint_type,
            plant_id=plant_id,
            coal_company_id=coal_company_id,
            document_id=document.id,
            annual_contract_quantity_mt=row.quantity_mt,
            contract_start_date=None,
            contract_end_date=row.valid_to,
            is_active=False,

            # new columns
            fiscal_year=fiscal_year,
            raw_source_name=row.raw_source_name,
            coal_company=row.coal_company,
            quantity_lac_mt=row.quantity_lac_mt,
            quantity_mt=row.quantity_mt,
            valid_to=row.valid_to,
            remarks=row.remarks,
            extraction_confidence=confidence,
            parser_notes=parser_note,
            status="PENDING_REVIEW"
        )
        created_records.append(record)

    if any_needs_review:
        document.needs_review = True
        document.review_status = "needs_review"
    else:
        document.needs_review = False
        document.review_status = "approved"

    db.flush()

    audit_service.record(
        db,
        entity_type="document",
        entity_id=document.id,
        action="extract",
        after={
            "document_type": document.document_type,
            "records_extracted": len(created_records),
            "any_needs_review": any_needs_review,
        },
    )

    return created_records, notes


def get_document_extraction(db: Session, document_id: uuid.UUID) -> tuple[Document, list[object]]:
    from app.modules.constraints.models import FSAConstraint
    from app.modules.landed_cost.models import LandedCost

    document = get_document_or_404(db, document_id)
    if document.document_type == "FSA_BRIDGE_LINKAGE_DOCUMENT":
        stmt = select(FSAConstraint).where(FSAConstraint.document_id == document_id)
        records = list(db.execute(stmt).scalars().all())
    elif document.document_type == "LANDED_COST_DOCUMENT":
        stmt = select(LandedCost).where(LandedCost.document_id == document_id)
        records = list(db.execute(stmt).scalars().all())
    else:
        raise ValidationFailedError(
            "Extraction is only supported for FSA_BRIDGE_LINKAGE_DOCUMENT or LANDED_COST_DOCUMENT."
        )

    return document, records


def extract_landed_cost_document(db: Session, document_id: uuid.UUID) -> tuple[list[object], list[str]]:
    from sqlalchemy import delete

    from app.modules.documents.landed_cost_parser import parse_landed_cost_pdf
    from app.modules.landed_cost.models import LandedCost

    document = get_document_or_404(db, document_id)
    if document.document_type != "LANDED_COST_DOCUMENT":
        raise ValidationFailedError(
            f"Extraction is only supported for document type 'LANDED_COST_DOCUMENT', "
            f"but got '{document.document_type}'."
        )

    try:
        with open(document.storage_path, "rb") as f:
            pdf_bytes = f.read()
    except Exception as e:
        raise ValidationFailedError(f"Failed to read file from storage: {e}") from e

    records, notes = parse_landed_cost_pdf(pdf_bytes)

    # Idempotent re-extraction: clear any existing landed cost records for this document
    db.execute(delete(LandedCost).where(LandedCost.document_id == document_id))
    db.flush()

    if not records:
        document.needs_review = True
        document.review_status = "needs_review"
        document.notes = "; ".join(notes) or "No landed cost rows could be parsed."
        db.flush()
        return [], notes

    created_records = []
    any_needs_review = False

    MAP_RAW_PLANT_TO_CODE = {
        "atps": "ANPARA-A",
        "a tps": "ANPARA-A",
        "anpara-a": "ANPARA-A",
        "btps": "ANPARA-B",
        "b tps": "ANPARA-B",
        "anpara-b": "ANPARA-B",
        "dtps": "ANPARA-D",
        "d tps": "ANPARA-D",
        "anpara-d": "ANPARA-D"
    }


    for row in records:
        # Resolve plant
        plant_id = None
        normalized_raw = row.raw_source_name.strip().lower()
        plant_code = MAP_RAW_PLANT_TO_CODE.get(normalized_raw)
        if plant_code:
            plant = db.execute(select(Plant).where(Plant.plant_code == plant_code)).scalars().first()
            if plant:
                plant_id = plant.id

        confidence = row.extraction_confidence
        notes_list = []
        if not plant_id:
            confidence = 0.0
            notes_list.append(f"Unresolved or ambiguous plant name: '{row.raw_source_name}'")

        if row.parser_notes:
            notes_list.append(row.parser_notes)

        if confidence < 1.0:
            any_needs_review = True

        parser_note = "; ".join(notes_list) if notes_list else None

        # Build landed cost DB record
        record = LandedCost(
            plant_id=plant_id,
            supplier_id=None,
            document_id=document.id,
            basic_cost=None,
            freight=None,
            taxes=None,
            other_cost=0.0,
            total_landed_cost=row.total_landed_cost_rs_per_mt,
            effective_from=row.effective_from,
            effective_to=row.effective_to,
            is_active=False,

            # review fields
            raw_source_name=row.raw_source_name,
            weighted_avg_gcv_kcal_per_kg=row.weighted_avg_gcv_kcal_per_kg,
            cost_basis="CERTIFIED_WEIGHTED_AVERAGE",
            extraction_confidence=confidence,
            parser_notes=parser_note,
            status="PENDING_REVIEW",
            needs_review=(plant_id is None or confidence < 1.0)
        )

        db.add(record)
        created_records.append(record)

    if any_needs_review or len(notes) > 0:
        document.needs_review = True
        document.review_status = "needs_review"
    else:
        document.needs_review = False
        document.review_status = "approved"

    db.flush()

    # Log audit event
    audit_service.record(
        db,
        entity_type="document",
        entity_id=document.id,
        action="extract_landed_cost",
        before={"extracted": False},
        after={
            "extracted": True,
            "record_count": len(created_records),
            "notes": notes,
        },
    )

    return created_records, notes


