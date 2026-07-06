"""Validation summary: aggregates missing/invalid/expired/warning conditions
across daily stock, Variable Cost, FSA/Bridge Linkage, and Landed Cost data.

This module is read-only: it reports issues, it never mutates data.
"""

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.constraints.models import FSAConstraint
from app.modules.daily_stock import repository as daily_stock_repository
from app.modules.documents import repository as documents_repository
from app.modules.landed_cost.models import LandedCost
from app.modules.master_data.models import Plant
from app.modules.validation.schemas import ValidationIssue


def build_validation_summary(db: Session) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    today = date.today()

    # 1. Missing / warning daily stock for active plants
    for plant, record in daily_stock_repository.latest_per_active_plant(db):
        if record is None:
            issues.append(
                ValidationIssue(
                    category="missing_daily_stock",
                    severity="critical",
                    plant_id=plant.id,
                    plant_code=plant.plant_code,
                    message=f"No daily stock record has ever been submitted for plant '{plant.plant_code}'.",
                )
            )
            continue
        if record.validation_status == "warning":
            issues.append(
                ValidationIssue(
                    category="stock_reconciliation_warning",
                    severity="warning",
                    plant_id=plant.id,
                    plant_code=plant.plant_code,
                    message=(
                        f"Plant '{plant.plant_code}' has a reconciliation mismatch of "
                        f"{float(record.reconciliation_difference_mt):.3f} MT on {record.report_date}."
                    ),
                    reference_date=record.report_date,
                )
            )

    # 2. Missing Variable Cost for active plants
    plants = list(db.execute(select(Plant).where(Plant.is_active.is_(True))).scalars().all())
    latest_vc_by_plant = {vc.plant_id for vc in documents_repository.latest_variable_cost_per_plant(db)}
    for plant in plants:
        if plant.id not in latest_vc_by_plant:
            issues.append(
                ValidationIssue(
                    category="missing_variable_cost",
                    severity="warning",
                    plant_id=plant.id,
                    plant_code=plant.plant_code,
                    message=f"No approved Variable Cost record is available for plant '{plant.plant_code}'.",
                )
            )

    # 3. Rows still needing manual review
    review_docs, review_total = documents_repository.list_documents(db, needs_review=True, limit=500)
    for doc in review_docs:
        issues.append(
            ValidationIssue(
                category="document_needs_review",
                severity="warning",
                plant_id=doc.plant_id,
                plant_code=None,
                message=f"Document '{doc.original_filename}' ({doc.document_type}) is pending manual review.",
            )
        )

    # 4. Expired or soon-to-expire FSA / Bridge Linkage constraints
    constraints = list(
        db.execute(select(FSAConstraint).where(FSAConstraint.is_active.is_(True))).scalars().all()
    )
    for c in constraints:
        if c.contract_end_date < today:
            plant = db.get(Plant, c.plant_id)
            issues.append(
                ValidationIssue(
                    category="expired_constraint",
                    severity="critical",
                    plant_id=c.plant_id,
                    plant_code=plant.plant_code if plant else None,
                    message=(
                        f"{c.constraint_type} constraint for plant "
                        f"'{plant.plant_code if plant else c.plant_id}' expired on {c.contract_end_date}."
                    ),
                    reference_date=c.contract_end_date,
                )
            )

    # 5. Missing landed cost for active plants
    active_plant_ids_with_landed_cost = {
        lc.plant_id
        for lc in db.execute(select(LandedCost).where(LandedCost.is_active.is_(True))).scalars().all()
    }
    for plant in plants:
        if plant.id not in active_plant_ids_with_landed_cost:
            issues.append(
                ValidationIssue(
                    category="missing_landed_cost",
                    severity="warning",
                    plant_id=plant.id,
                    plant_code=plant.plant_code,
                    message=f"No active Landed Cost record is available for plant '{plant.plant_code}'.",
                )
            )

    return issues


def generate_summary(db: Session):
    from app.modules.validation.schemas import ValidationSummary

    issues = build_validation_summary(db)
    return ValidationSummary(
        generated_at=datetime.now(UTC).isoformat(),
        total_issues=len(issues),
        issues=issues,
    )
