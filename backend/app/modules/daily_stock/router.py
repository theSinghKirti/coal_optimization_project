import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams
from app.core.database import get_db
from app.modules.daily_stock import service
from app.modules.daily_stock.schemas import (
    DailyStockCreate,
    DailyStockRead,
    DailyStockUpdate,
    LatestStockSummaryItem,
)

router = APIRouter(prefix="/daily-stock", tags=["Daily Stock"])


@router.post("", response_model=DailyStockRead, status_code=status.HTTP_201_CREATED)
def create_daily_stock(payload: DailyStockCreate, db: Session = Depends(get_db)):
    record = service.create_daily_stock(db, payload)
    db.commit()
    return record


@router.get("", response_model=Page[DailyStockRead])
def list_daily_stock(
    plant_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    validation_status: str | None = Query(default=None, pattern="^(ok|warning)$"),
    page_params: PageParams = Depends(),
    db: Session = Depends(get_db),
):
    items, total = service.list_daily_stock(
        db,
        plant_id=plant_id,
        date_from=date_from,
        date_to=date_to,
        validation_status=validation_status,
        limit=page_params.page_size,
        offset=page_params.offset,
    )
    return Page(items=items, page=page_params.page, page_size=page_params.page_size, total=total)


@router.get("/summary/latest", response_model=list[LatestStockSummaryItem])
def latest_summary(db: Session = Depends(get_db)):
    return service.latest_summary(db)


@router.get("/{record_id}", response_model=DailyStockRead)
def get_daily_stock(record_id: uuid.UUID, db: Session = Depends(get_db)):
    return service.get_or_404(db, record_id)


@router.patch("/{record_id}", response_model=DailyStockRead)
def update_daily_stock(record_id: uuid.UUID, payload: DailyStockUpdate, db: Session = Depends(get_db)):
    record = service.update_daily_stock(db, record_id, payload)
    db.commit()
    return record
