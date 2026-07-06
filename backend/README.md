# UPRVUNL Coal Optimization & Decision Support Platform (CODSP) — Backend

Backend MVP for centralizing coal operational data, validating it, running a
deterministic coal-allocation optimization, and exposing recommendations and
dashboard data for a future React/Vite frontend.

This backend deliberately does **not** include authentication, a frontend,
OCR, or any AI/LLM component — see [`IMPLEMENTATION_REPORT.md`](./IMPLEMENTATION_REPORT.md)
for the full list of in-scope vs. deferred features and the reasoning behind
every design decision.

## Stack

FastAPI · PostgreSQL 16 · SQLAlchemy 2.x · Alembic · Pydantic v2 · PyMuPDF ·
PuLP + CBC · APScheduler · pytest · Ruff.

## Project layout

```
backend/
  app/
    core/            # settings, DB engine/session, centralized exception handling
    common/           # shared mixins (UUID PK, UTC timestamps) and pagination
    modules/
      health/         # GET /health
      master_data/    # plants, plant aliases, coal companies, suppliers
      daily_stock/    # daily coal stock entry + reconciliation validation
      documents/      # static document archive + deterministic Variable Cost PDF parser
      constraints/    # FSA / Bridge Linkage constraints
      landed_cost/    # landed coal cost records
      validation/     # read-only validation summary (missing/expired/warning data)
      audit/          # append-only audit log + generic `record()` helper
      optimization/   # PuLP/CBC solver + run/allocation persistence
      recommendations/# recommendation rules triggered by optimization + stock data
      dashboard/      # aggregated summary API for the frontend
      scheduler/      # UPSLDC ingestion adapter + APScheduler wiring
    main.py           # FastAPI app, router wiring, lifespan (scheduler start/stop)
  alembic/            # migrations (env.py wired to app settings + all models)
  scripts/seed.py      # idempotent master-data seed script (run manually)
  tests/               # pytest suite against a real PostgreSQL test database
  storage/documents/   # local filesystem document storage (V1)
  requirements.txt
  docker-compose.yml
  Dockerfile
  .env.example
```

Each module follows the same internal shape: `models.py` (SQLAlchemy ORM) →
`repository.py` (raw queries) → `service.py` (business rules, calls the audit
service) → `router.py` (thin FastAPI routes, Pydantic schemas in `schemas.py`).

## Getting started (Docker Compose — recommended)

```bash
cd backend
cp .env.example .env        # edit POSTGRES_PASSWORD etc. if you want
docker compose up --build
```

This starts PostgreSQL, runs `alembic upgrade head`, and starts the API on
`http://localhost:8000`. Swagger UI: `http://localhost:8000/docs`.

Seeding is **not** automatic (by design). After the containers are up, run:

```bash
docker compose exec api python -m scripts.seed
```

## Getting started (running the API locally against dockerized Postgres)

```bash
cd backend
cp .env.example .env
# Edit .env: set DATABASE_URL host to "localhost" instead of "db"
docker compose up -d db
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload
```

## Running tests

Tests run against a **real PostgreSQL** database (never SQLite), matching
the project's "PostgreSQL only" rule. They automatically create/use a
`codsp_test_db` database (derived from `DATABASE_URL`) and wrap each test in
a rolled-back transaction, so your `codsp_db` data is never touched.

```bash
# Postgres must be reachable (e.g. `docker compose up -d db`)
# and the connecting user needs CREATEDB privilege the first time.
pytest -v
```

## Linting

```bash
ruff check .
ruff format --check .
```

## Key domain rules implemented

- **Daily Stock**: `Expected Closing = Opening + Receipt - Consumption`;
  mismatches beyond `STOCK_RECONCILIATION_TOLERANCE_MT` are flagged
  `warning` and require remarks; one record per plant/date; negative values
  and unknown plants are rejected.
- **Variable Cost PDFs**: PyMuPDF-only, deterministic, line-based parsing;
  only rows matching a known Plant/PlantAlias are kept; non-UPRVUNL rows
  (NTPC/private/IPP keywords) are always discarded; ambiguous rows are kept
  but flagged `needs_review`; duplicate files are rejected by SHA-256 hash;
  historical rows are append-only and never overwritten.
- **FSA / Bridge Linkage**: contract end date cannot precede start date;
  only `is_active` contracts whose date range covers "today" are used by the
  optimizer.
- **Landed Cost**: `Total = Basic + Freight + Taxes + Other`; never
  fabricated — a plant with no active landed cost is reported as missing
  data rather than assigned an invented number.
- **Optimization**: PuLP + CBC, minimizes `Σ allocation × landed cost`,
  monthly demand proxy `max(0, 30 × consumption − closing stock)`, ACQ cap
  `monthly_cap_mt` or `annual_contract_quantity_mt × 30 / 365`, and a market
  top-up slack variable priced at `max(landed cost) × 1.20` (or the
  configurable fallback) so the model always stays feasible. Missing
  required data marks the run `incomplete_data` instead of guessing.

## API groups (all under `/api/v1`)

See `IMPLEMENTATION_REPORT.md` for the full endpoint list mapped to the
Backend Blueprint's required API groups, and for notes on assumptions made
where the source documents didn't fully specify a behavior.
