from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.validation import service
from app.modules.validation.schemas import ValidationSummary

router = APIRouter(prefix="/validation", tags=["Validation"])


@router.get("/summary", response_model=ValidationSummary)
def validation_summary(db: Session = Depends(get_db)):
    return service.generate_summary(db)
