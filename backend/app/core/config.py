"""Centralized application settings loaded from environment variables (.env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Application
    app_name: str = "UPRVUNL CODSP Backend"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+psycopg://codsp_user:change_me@localhost:5432/codsp_db"

    # Storage
    document_storage_path: str = "./storage/documents"

    # Daily stock validation
    stock_reconciliation_tolerance_mt: float = 0.01

    # Optimization
    optimization_fallback_landed_cost: float = 0.0
    optimization_market_topup_multiplier: float = 1.20
    optimization_demand_horizon_days: int = 30

    # UPSLDC Scheduler
    upsldc_source_url: str = "https://upsldc.org/variable-cost"
    upsldc_max_pdfs_per_run: int = 10
    scheduler_enabled: bool = False
    scheduler_cron_hour: int = 6
    scheduler_cron_minute: int = 0


@lru_cache
def get_settings() -> Settings:
    return Settings()
