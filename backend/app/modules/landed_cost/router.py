import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams
from app.core.database import get_db
from app.modules.landed_cost import service
from app.modules.landed_cost.schemas import (
    LandedCostCreate,
    LandedCostRead,
    LandedCostReview,
    LandedCostUpdate,
)

router = APIRouter(prefix="/landed-costs", tags=["Landed Cost"])


@router.post("", response_model=LandedCostRead, status_code=status.HTTP_201_CREATED)
def create_landed_cost(payload: LandedCostCreate, db: Session = Depends(get_db)):
    record = service.create_landed_cost(db, payload)
    db.commit()
    return record


@router.get("/latest", response_model=list[LandedCostRead])
def latest_landed_costs(db: Session = Depends(get_db)):
    return service.latest_landed_costs(db)


@router.get("", response_model=Page[LandedCostRead])
def list_landed_costs(
    plant_id: uuid.UUID | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    page_params: PageParams = Depends(),
    db: Session = Depends(get_db),
):
    items, total = service.list_landed_costs(
        db,
        plant_id=plant_id,
        is_active=is_active,
        limit=page_params.page_size,
        offset=page_params.offset,
    )
    return Page(items=items, page=page_params.page, page_size=page_params.page_size, total=total)


@router.get("/{record_id}", response_model=LandedCostRead)
def get_landed_cost(record_id: uuid.UUID, db: Session = Depends(get_db)):
    return service.get_or_404(db, record_id)


@router.patch("/{record_id}", response_model=LandedCostRead)
def update_landed_cost(record_id: uuid.UUID, payload: LandedCostUpdate, db: Session = Depends(get_db)):
    record = service.update_landed_cost(db, record_id, payload)
    db.commit()
    return record


@router.post("/{record_id}/review", response_model=LandedCostRead)
def review_landed_cost(record_id: uuid.UUID, payload: LandedCostReview, db: Session = Depends(get_db)):
    record = service.review_landed_cost(db, record_id, payload)
    db.commit()
    return record

