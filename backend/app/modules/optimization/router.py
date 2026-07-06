import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams
from app.core.database import get_db
from app.modules.optimization import service
from app.modules.optimization.schemas import (
    AllocationResultRead,
    OptimizationRunDetail,
    OptimizationRunRead,
    OptimizationRunRequest,
)

router = APIRouter(prefix="/optimization", tags=["Optimization"])


@router.post("/run", response_model=OptimizationRunDetail, status_code=status.HTTP_201_CREATED)
def run_optimization(
    payload: OptimizationRunRequest = OptimizationRunRequest(), db: Session = Depends(get_db)
):
    run = service.run_optimization(db, payload)
    db.commit()
    return service.get_run_or_404(db, run.id)


@router.get("/runs", response_model=Page[OptimizationRunRead])
def list_runs(page_params: PageParams = Depends(), db: Session = Depends(get_db)):
    items, total = service.list_runs(db, limit=page_params.page_size, offset=page_params.offset)
    return Page(items=items, page=page_params.page, page_size=page_params.page_size, total=total)


@router.get("/latest", response_model=OptimizationRunDetail)
def latest_run(db: Session = Depends(get_db)):
    return service.get_latest_run_or_404(db)


@router.get("/runs/{run_id}/allocations", response_model=list[AllocationResultRead])
def get_run_allocations(run_id: uuid.UUID, db: Session = Depends(get_db)):
    run = service.get_run_or_404(db, run_id)
    return run.allocations
