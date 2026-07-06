import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams
from app.core.database import get_db
from app.modules.constraints import service
from app.modules.constraints.schemas import (
    FSAConstraintCreate,
    FSAConstraintRead,
    FSAConstraintReview,
    FSAConstraintUpdate,
)

router = APIRouter(prefix="/fsa-constraints", tags=["FSA & Bridge Linkage"])



@router.post("", response_model=FSAConstraintRead, status_code=status.HTTP_201_CREATED)
def create_constraint(payload: FSAConstraintCreate, db: Session = Depends(get_db)):
    record = service.create_constraint(db, payload)
    db.commit()
    return record


@router.get("", response_model=Page[FSAConstraintRead])
def list_constraints(
    plant_id: uuid.UUID | None = Query(default=None),
    constraint_type: str | None = Query(default=None, pattern="^(FSA|BRIDGE_LINKAGE)$"),
    is_active: bool | None = Query(default=None),
    page_params: PageParams = Depends(),
    db: Session = Depends(get_db),
):
    items, total = service.list_constraints(
        db,
        plant_id=plant_id,
        constraint_type=constraint_type,
        is_active=is_active,
        limit=page_params.page_size,
        offset=page_params.offset,
    )
    return Page(items=items, page=page_params.page, page_size=page_params.page_size, total=total)


@router.get("/{record_id}", response_model=FSAConstraintRead)
def get_constraint(record_id: uuid.UUID, db: Session = Depends(get_db)):
    return service.get_or_404(db, record_id)


@router.patch("/{record_id}", response_model=FSAConstraintRead)
def update_constraint(record_id: uuid.UUID, payload: FSAConstraintUpdate, db: Session = Depends(get_db)):
    record = service.update_constraint(db, record_id, payload)
    db.commit()
    return record


@router.post("/{record_id}/review", response_model=FSAConstraintRead)
def review_constraint(record_id: uuid.UUID, payload: FSAConstraintReview, db: Session = Depends(get_db)):
    record = service.review_constraint(db, record_id, payload)
    db.commit()
    return record

