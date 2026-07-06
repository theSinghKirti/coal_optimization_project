import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams
from app.core.database import get_db
from app.core.exceptions import ValidationFailedError
from app.modules.documents import service
from app.modules.documents.schemas import (
    DocumentRead,
    DocumentType,
    VariableCostRead,
    VariableCostReviewUpdate,
    VariableCostUploadResult,
)

router = APIRouter(tags=["Documents & Variable Cost"])

_MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


@router.post("/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    document_type: DocumentType = Form(...),
    plant_id: uuid.UUID | None = Form(default=None),
    notes: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise ValidationFailedError("File exceeds the maximum allowed upload size (25 MB).")
    document = service.upload_document(
        db,
        content=content,
        original_filename=file.filename or "document",
        document_type=document_type,
        plant_id=plant_id,
        notes=notes,
    )
    db.commit()
    return document


@router.get("/documents", response_model=Page[DocumentRead])
def list_documents(
    document_type: str | None = Query(default=None),
    needs_review: bool | None = Query(default=None),
    page_params: PageParams = Depends(),
    db: Session = Depends(get_db),
):
    items, total = service.list_documents(
        db,
        document_type=document_type,
        needs_review=needs_review,
        limit=page_params.page_size,
        offset=page_params.offset,
    )
    return Page(items=items, page=page_params.page, page_size=page_params.page_size, total=total)


@router.get("/documents/{document_id}", response_model=DocumentRead)
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    return service.get_document_or_404(db, document_id)


@router.post(
    "/variable-cost/upload",
    response_model=VariableCostUploadResult,
    status_code=status.HTTP_201_CREATED,
)
async def upload_variable_cost_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise ValidationFailedError("File exceeds the maximum allowed upload size (25 MB).")
    document, rows, notes = service.upload_and_parse_variable_cost_pdf(
        db, content=content, original_filename=file.filename or "variable_cost.pdf"
    )
    db.commit()
    return VariableCostUploadResult(
        document=document,
        parsed_rows=rows,
        rows_needing_review=sum(1 for r in rows if r.needs_review),
        parser_notes=notes,
    )


@router.get("/variable-cost", response_model=Page[VariableCostRead])
def list_variable_costs(
    plant_id: uuid.UUID | None = Query(default=None),
    needs_review: bool | None = Query(default=None),
    page_params: PageParams = Depends(),
    db: Session = Depends(get_db),
):
    items, total = service.list_variable_costs(
        db,
        plant_id=plant_id,
        needs_review=needs_review,
        limit=page_params.page_size,
        offset=page_params.offset,
    )
    return Page(items=items, page=page_params.page, page_size=page_params.page_size, total=total)


@router.get("/variable-cost/latest", response_model=list[VariableCostRead])
def latest_variable_costs(db: Session = Depends(get_db)):
    return service.latest_variable_costs(db)


@router.patch("/variable-cost/{vc_id}/review", response_model=VariableCostRead)
def review_variable_cost(vc_id: uuid.UUID, payload: VariableCostReviewUpdate, db: Session = Depends(get_db)):
    vc = service.review_variable_cost(db, vc_id, plant_id=payload.plant_id, needs_review=payload.needs_review)
    db.commit()
    return vc
