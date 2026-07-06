"""FastAPI application entrypoint: wiring, middleware, routers, lifespan."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.modules.audit.router import router as audit_router
from app.modules.constraints.router import router as constraints_router
from app.modules.daily_stock.router import router as daily_stock_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.documents.router import router as documents_router
from app.modules.health.router import router as health_router
from app.modules.landed_cost.router import router as landed_cost_router
from app.modules.master_data.router import router as master_data_router
from app.modules.optimization.router import router as optimization_router
from app.modules.recommendations.router import router as recommendations_router
from app.modules.scheduler.jobs import shutdown_scheduler, start_scheduler
from app.modules.scheduler.router import router as scheduler_router
from app.modules.validation.router import router as validation_router

settings = get_settings()

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Backend API for the UPRVUNL Coal Optimization & Decision Support Platform (CODSP). "
        "Centralizes coal operational data, validates it, runs deterministic coal-allocation "
        "optimization, and exposes recommendations and dashboard data for a future frontend."
    ),
    lifespan=lifespan,
)

register_exception_handlers(app)

_prefix = settings.api_v1_prefix

app.include_router(health_router, prefix=_prefix)
app.include_router(master_data_router, prefix=_prefix)
app.include_router(daily_stock_router, prefix=_prefix)
app.include_router(documents_router, prefix=_prefix)
app.include_router(constraints_router, prefix=_prefix)
app.include_router(landed_cost_router, prefix=_prefix)
app.include_router(validation_router, prefix=_prefix)
app.include_router(audit_router, prefix=_prefix)
app.include_router(optimization_router, prefix=_prefix)
app.include_router(recommendations_router, prefix=_prefix)
app.include_router(dashboard_router, prefix=_prefix)
app.include_router(scheduler_router, prefix=_prefix)
