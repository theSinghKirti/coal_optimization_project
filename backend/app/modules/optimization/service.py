"""Coal allocation optimization workflow.

Orchestrates: gather inputs -> run the deterministic PuLP/CBC solver ->
persist an auditable run snapshot + allocation results -> generate
recommendations. Never fabricates suppliers, contracts, or costs; any plant
or contract source with missing required data is excluded from the model
and reported, and the overall run is marked `incomplete_data` when that
happens.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.audit import service as audit_service
from app.modules.constraints import repository as constraints_repository
from app.modules.daily_stock import repository as daily_stock_repository
from app.modules.landed_cost import repository as landed_cost_repository
from app.modules.master_data.models import Plant
from app.modules.optimization import repository
from app.modules.optimization.schemas import OptimizationRunRequest
from app.modules.optimization.solver import ContractSource, PlantDemand, solve
from app.modules.recommendations import service as recommendations_service

settings = get_settings()


def _monthly_acq_cap(constraint) -> float:
    if constraint.monthly_cap_mt:
        return float(constraint.monthly_cap_mt)
    return float(constraint.annual_contract_quantity_mt) * 30 / 365


def _resolve_landed_cost_for_source(
    db: Session, plant_id: uuid.UUID, supplier_id: uuid.UUID | None, as_of: date
):
    candidates = landed_cost_repository.list_active_for_plant(db, plant_id, as_of=as_of)
    if supplier_id:
        matching = [c for c in candidates if c.supplier_id == supplier_id]
        if matching:
            return max(matching, key=lambda c: c.effective_from)
    # fall back to a plant-level (no specific supplier) landed cost record
    plant_level = [c for c in candidates if c.supplier_id is None]
    if plant_level:
        return max(plant_level, key=lambda c: c.effective_from)
    if candidates:
        return max(candidates, key=lambda c: c.effective_from)
    return None


def run_optimization(db: Session, payload: OptimizationRunRequest):
    today = date.today()
    now = datetime.now(UTC)

    stmt = select(Plant).where(Plant.is_active.is_(True))
    if payload.plant_ids:
        stmt = stmt.where(Plant.id.in_(payload.plant_ids))
    plants = list(db.execute(stmt).scalars().all())

    demands: list[PlantDemand] = []
    sources: list[ContractSource] = []
    missing_data_notes: list[str] = []
    plant_stock_info: dict[str, dict] = {}

    for plant in plants:
        # latest stock record for this plant
        stock_rows, _ = daily_stock_repository.list_records(db, plant_id=plant.id, limit=1, offset=0)
        latest = stock_rows[0] if stock_rows else None

        if latest is None:
            missing_data_notes.append(f"Plant '{plant.plant_code}': missing daily stock; excluded from run.")
            plant_stock_info[str(plant.id)] = {"stock_days": None, "missing_stock": True}
            continue

        consumption = float(latest.consumption_mt)
        closing_stock = float(latest.closing_stock_mt)
        monthly_demand = max(0.0, settings.optimization_demand_horizon_days * consumption - closing_stock)
        stock_days = (closing_stock / consumption) if consumption > 0 else None
        plant_stock_info[str(plant.id)] = {"stock_days": stock_days, "missing_stock": False}

        if monthly_demand <= 0:
            # No shortfall this month; nothing to allocate, and no need to
            # resolve constraints/landed cost data for this plant.
            continue

        active_constraints = constraints_repository.list_active_for_plant(db, plant.id, as_of=today)
        active_landed_costs = landed_cost_repository.list_active_for_plant(db, plant.id, as_of=today)

        plant_sources: list[ContractSource] = []
        for constraint in active_constraints:
            landed_cost_record = _resolve_landed_cost_for_source(db, plant.id, constraint.supplier_id, today)
            if landed_cost_record is None:
                missing_data_notes.append(
                    f"Plant '{plant.plant_code}': no Landed Cost available for "
                    f"{constraint.constraint_type} constraint {constraint.id}; source excluded."
                )
                continue
            plant_sources.append(
                ContractSource(
                    source_id=str(constraint.id),
                    plant_id=str(plant.id),
                    supplier_id=str(constraint.supplier_id) if constraint.supplier_id else None,
                    monthly_cap_mt=_monthly_acq_cap(constraint),
                    landed_cost_per_mt=float(landed_cost_record.total_landed_cost),
                    constraint_type=constraint.constraint_type,
                )
            )

        if active_landed_costs:
            market_topup_cost = max(float(c.total_landed_cost) for c in active_landed_costs) * (
                settings.optimization_market_topup_multiplier
            )
        elif settings.optimization_fallback_landed_cost > 0:
            market_topup_cost = settings.optimization_fallback_landed_cost * (
                settings.optimization_market_topup_multiplier
            )
            missing_data_notes.append(
                f"Plant '{plant.plant_code}': no Landed Cost record found; using configured fallback "
                f"cost for market top-up pricing."
            )
        else:
            missing_data_notes.append(
                f"Plant '{plant.plant_code}': no Landed Cost record and no fallback cost configured; "
                f"excluded from run."
            )
            continue

        demands.append(
            PlantDemand(
                plant_id=str(plant.id),
                monthly_demand_mt=monthly_demand,
                market_topup_cost_per_mt=market_topup_cost,
            )
        )
        sources.extend(plant_sources)

    if not demands and not missing_data_notes:
        # No active plant currently has a shortfall; nothing to optimize this run.
        run = repository.create_run(
            db,
            run_timestamp=now,
            status="completed",
            triggered_by=payload.triggered_by,
            solver_status="no_demand",
            total_estimated_cost=0,
            notes="No plant currently has a monthly coal shortfall requiring allocation.",
            input_snapshot={"plants_considered": len(plants)},
        )
        db.flush()
        audit_service.record(
            db,
            entity_type="optimization_run",
            entity_id=run.id,
            action="optimize",
            after={"status": run.status},
        )
        return run

    solve_result = solve(demands, sources)

    if solve_result.status == "no_sources":
        status_value = "incomplete_data"
        solver_status = "no_sources"
    elif solve_result.status == "optimal":
        status_value = "incomplete_data" if missing_data_notes else "completed"
        solver_status = "optimal"
    else:
        status_value = "failed"
        solver_status = solve_result.status

    run = repository.create_run(
        db,
        run_timestamp=now,
        status=status_value,
        triggered_by=payload.triggered_by,
        solver_status=solver_status,
        total_estimated_cost=solve_result.total_estimated_cost if solve_result.status == "optimal" else None,
        notes="; ".join(missing_data_notes) if missing_data_notes else None,
        input_snapshot={
            "demands": [d.__dict__ for d in demands],
            "source_count": len(sources),
        },
    )
    db.flush()

    if solve_result.status == "optimal":
        for line in solve_result.allocations:
            repository.add_allocation(
                db,
                run_id=run.id,
                plant_id=uuid.UUID(line.plant_id),
                supplier_id=uuid.UUID(line.supplier_id) if line.supplier_id else None,
                allocation_type=line.allocation_type,
                quantity_mt=line.quantity_mt,
                unit_cost=line.unit_cost,
                estimated_cost=line.estimated_cost,
                acq_utilization_pct=line.acq_utilization_pct,
            )

    db.flush()

    recommendations_service.generate_for_run(
        db,
        run=run,
        allocations=solve_result.allocations if solve_result.status == "optimal" else [],
        plant_stock_info=plant_stock_info,
        missing_data_notes=missing_data_notes,
    )

    audit_service.record(
        db,
        entity_type="optimization_run",
        entity_id=run.id,
        action="optimize",
        after={"status": run.status, "solver_status": run.solver_status},
    )
    return run


def get_run_or_404(db: Session, run_id: uuid.UUID):
    from app.core.exceptions import NotFoundError

    run = repository.get_run(db, run_id)
    if not run:
        raise NotFoundError("Optimization run not found.")
    return run


def list_runs(db: Session, *, limit: int, offset: int):
    return repository.list_runs(db, limit=limit, offset=offset)


def get_latest_run_or_404(db: Session):
    from app.core.exceptions import NotFoundError

    run = repository.get_latest_run(db)
    if not run:
        raise NotFoundError("No optimization runs have been executed yet.")
    return run
