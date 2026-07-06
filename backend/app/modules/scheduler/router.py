from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.scheduler.schemas import IngestionRunResult
from app.modules.scheduler.upsldc_adapter import run_ingestion

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


@router.post("/variable-cost/run-now", response_model=IngestionRunResult)
def run_now(db: Session = Depends(get_db)):
    """Manually triggers the UPSLDC Variable Cost ingestion job on demand.

    Safe to call even if the UPSLDC site is unreachable or SCHEDULER_ENABLED=false;
    this endpoint always runs the check/download/parse workflow once, synchronously.
    """
    result = run_ingestion(db)
    return IngestionRunResult(
        source_reachable=result.source_reachable,
        discovered_links=len(result.discovered_links),
        downloaded=result.downloaded,
        skipped_duplicates=result.skipped_duplicates,
        failed_downloads=result.failed_downloads,
        documents_created=result.documents_created,
        notes=result.notes,
    )
