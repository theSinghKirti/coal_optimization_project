"""Aggregated read-only dashboard summary for the future React/Vite frontend."""

from sqlalchemy.orm import Session

from app.modules.daily_stock import repository as daily_stock_repository
from app.modules.dashboard.schemas import DashboardPlantSnapshot, DashboardSummary
from app.modules.optimization import repository as optimization_repository
from app.modules.recommendations import repository as recommendations_repository


def build_dashboard_summary(db: Session) -> DashboardSummary:
    rows = daily_stock_repository.latest_per_active_plant(db)

    snapshots = []
    plants_with_warnings = 0
    plants_missing_stock = 0

    for plant, record in rows:
        stock_days = None
        status_value = None
        if record is None:
            plants_missing_stock += 1
        else:
            status_value = record.validation_status
            if status_value == "warning":
                plants_with_warnings += 1
            if float(record.consumption_mt) > 0:
                stock_days = float(record.closing_stock_mt) / float(record.consumption_mt)
        snapshots.append(
            DashboardPlantSnapshot(
                plant_id=plant.id,
                plant_code=plant.plant_code,
                plant_name=plant.plant_name,
                stock_days=stock_days,
                validation_status=status_value,
            )
        )

    _, open_recommendations_total = recommendations_repository.list_recommendations(db, limit=1, offset=0)
    _, critical_total = recommendations_repository.list_recommendations(
        db, severity="critical", limit=1, offset=0
    )

    latest_run = optimization_repository.get_latest_run(db)

    return DashboardSummary(
        total_plants=len(rows),
        active_plants=len(rows),
        plants_with_warnings=plants_with_warnings,
        plants_missing_stock=plants_missing_stock,
        open_recommendations=open_recommendations_total,
        critical_recommendations=critical_total,
        latest_optimization_run_id=latest_run.id if latest_run else None,
        latest_optimization_status=latest_run.status if latest_run else None,
        latest_optimization_total_cost=(
            float(latest_run.total_estimated_cost)
            if latest_run and latest_run.total_estimated_cost is not None
            else None
        ),
        plant_snapshots=snapshots,
    )
