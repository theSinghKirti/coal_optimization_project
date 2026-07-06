"""Recommendation generation rules, applied after every optimization run.

Trigger                     | Condition
-----------------------------|---------------------------------------------
Critical Stock                stock days < 1
Low Stock                     stock days < 3
ACQ Near Limit                utilization >= 90%
Market Top-up Required        market top-up quantity > 0
Missing Daily Stock           no recent stock record for an active plant
Missing Variable Cost         no latest VC available
Missing Landed Cost           no active landed cost for required allocation
Optimization Incomplete       required data missing
Optimization Failed           solver failure
"""

import uuid

from sqlalchemy.orm import Session

from app.modules.documents import repository as documents_repository
from app.modules.master_data.models import Plant
from app.modules.optimization.models import OptimizationRun
from app.modules.optimization.solver import AllocationLine
from app.modules.recommendations import repository


def generate_for_run(
    db: Session,
    *,
    run: OptimizationRun,
    allocations: list[AllocationLine],
    plant_stock_info: dict[str, dict],
    missing_data_notes: list[str],
) -> None:
    # Stock-condition recommendations
    for plant_id_str, info in plant_stock_info.items():
        plant_id = uuid.UUID(plant_id_str)
        if info.get("missing_stock"):
            repository.create(
                db,
                run_id=run.id,
                plant_id=plant_id,
                recommendation_type="missing_daily_stock",
                severity="critical",
                message="No recent daily stock record exists for this active plant.",
            )
            continue

        stock_days = info.get("stock_days")
        if stock_days is None:
            continue
        if stock_days < 1:
            repository.create(
                db,
                run_id=run.id,
                plant_id=plant_id,
                recommendation_type="critical_stock",
                severity="critical",
                message=f"Critical stock: only {stock_days:.2f} days of coal remaining.",
            )
        elif stock_days < 3:
            repository.create(
                db,
                run_id=run.id,
                plant_id=plant_id,
                recommendation_type="low_stock",
                severity="warning",
                message=f"Low stock: {stock_days:.2f} days of coal remaining.",
            )

    # ACQ near-limit + market top-up recommendations from allocation results
    for line in allocations:
        if line.acq_utilization_pct is not None and line.acq_utilization_pct >= 90:
            repository.create(
                db,
                run_id=run.id,
                plant_id=uuid.UUID(line.plant_id),
                recommendation_type="acq_near_limit",
                severity="warning",
                message=f"ACQ utilization at {line.acq_utilization_pct:.1f}% for this contract source.",
            )
        if line.allocation_type == "market_topup" and line.quantity_mt > 0:
            repository.create(
                db,
                run_id=run.id,
                plant_id=uuid.UUID(line.plant_id),
                recommendation_type="market_topup_required",
                severity="warning",
                message=f"Market/e-auction top-up of {line.quantity_mt:.2f} MT is required to meet demand.",
            )

    # Missing Variable Cost (dashboard/reporting context, not used in the objective)
    plants = db.query(Plant).filter(Plant.is_active.is_(True)).all()
    latest_vc_plant_ids = {vc.plant_id for vc in documents_repository.latest_variable_cost_per_plant(db)}
    for plant in plants:
        if plant.id not in latest_vc_plant_ids:
            repository.create(
                db,
                run_id=run.id,
                plant_id=plant.id,
                recommendation_type="missing_variable_cost",
                severity="warning",
                message="No approved Variable Cost record is available for operational reporting.",
            )

    # Missing-data / run-level recommendations
    for note in missing_data_notes:
        if "Landed Cost" in note:
            rec_type = "missing_landed_cost"
        else:
            rec_type = "optimization_incomplete"
        repository.create(
            db,
            run_id=run.id,
            plant_id=None,
            recommendation_type=rec_type,
            severity="warning",
            message=note,
        )

    if run.status == "failed":
        repository.create(
            db,
            run_id=run.id,
            plant_id=None,
            recommendation_type="optimization_failed",
            severity="critical",
            message=f"Solver could not find a feasible allocation (status: {run.solver_status}).",
        )
    elif run.status == "incomplete_data" and not missing_data_notes:
        repository.create(
            db,
            run_id=run.id,
            plant_id=None,
            recommendation_type="optimization_incomplete",
            severity="warning",
            message="Optimization completed with incomplete input data.",
        )


def list_recommendations(db: Session, **filters):
    return repository.list_recommendations(db, **filters)
