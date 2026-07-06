# Local Verification Report

**Date:** 2026-07-06  
**Python:** 3.11.9  
**OS:** Windows 11  

---

## 1. Project Structure Inspection

### Module layout (all consistent)
```
backend/
  app/
    common/          mixins.py  pagination.py
    core/            config.py  database.py  exceptions.py
    modules/
      audit/         models.py  repository.py  router.py  schemas.py  service.py
      constraints/   models.py  repository.py  router.py  schemas.py  service.py
      daily_stock/   models.py  repository.py  router.py  schemas.py  service.py
      dashboard/     router.py  schemas.py  service.py
      documents/     models.py  repository.py  router.py  schemas.py  service.py
                     storage.py  variable_cost_parser.py
      health/        router.py
      landed_cost/   models.py  repository.py  router.py  schemas.py  service.py
      master_data/   models.py  repository.py  router.py  schemas.py  service.py
      optimization/  models.py  repository.py  router.py  schemas.py  service.py  solver.py
      recommendations/ models.py  repository.py  router.py  schemas.py  service.py
      scheduler/     jobs.py  router.py  schemas.py  upsldc_adapter.py
      validation/    router.py  schemas.py  service.py
    main.py
  alembic/
    env.py  versions/e28cd7418010_initial_schema.py
  tests/
    conftest.py  test_daily_stock.py  test_fsa_constraints.py
    test_landed_cost.py  test_master_data.py  test_optimization.py
    test_variable_cost_parser.py  test_variable_cost_upload.py
  requirements.txt  pyproject.toml  docker-compose.yml  alembic.ini
```

### Import/naming consistency check
- All modules use plural file names: models.py, schemas.py
- All cross-module imports resolved correctly (no singular/plural mismatches)
- No circular imports detected
- All from app.modules.<module> import <submodule> patterns consistent
- Base class imported in all model files from app.core.database
- All ORM models properly registered on Base.metadata via alembic/env.py

---

## 2. Commands Run

```
pip install -r requirements.txt
python -c "import app.main; print('Import OK')"
python -m ruff check .
docker compose up -d db
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
# HTTP test of /docs and /api/v1/health
python -m pytest tests/ -v --tb=short
```

---

## 3. Errors Found & Fixes Applied

### Error 1: ImportError: DLL load failed while importing _extra (PyMuPDF)

**Root cause:** `variable_cost_parser.py` had `import fitz` at module level. On this Windows
machine, the PyMuPDF==1.24.10 native DLL (_extra) fails to load due to Windows Application 
Control policy. This crash propagated to every import that touched documents.service, 
blocking the entire FastAPI app from starting.

**Fix 1 - lazy import in variable_cost_parser.py:**
Moved `import fitz` from module-level to inside `extract_text_lines()` so a DLL failure does NOT
crash startup. The existing try/except in `parse_variable_cost_pdf()` already handles extraction
failures gracefully and marks documents as `needs_review`.

Before:
```python
import fitz  # PyMuPDF  (module level - line 26)
```

After:
```python
def extract_text_lines(pdf_bytes: bytes) -> list[str]:
    import fitz  # lazy import so a missing/blocked DLL doesn't crash startup
```

**Fix 2 - pin PyMuPDF version in requirements.txt:**
PyMuPDF==1.24.10 fails on this machine. Downgraded to PyMuPDF==1.23.26 (confirmed working).

```
- PyMuPDF==1.24.10
+ PyMuPDF==1.23.26
```

---

## 4. Static Checks Results

### Python import check
```
python -c "import app.main; print('Import OK')"
Import OK
```
RESULT: PASS

### Ruff check
```
python -m ruff check .
All checks passed!
```
RESULT: PASS - zero lint errors (rules: E, F, I, UP, B; ignoring B008)

---

## 5. Pytest Results

```
============================= test session info =============================
platform win32 -- Python 3.11.9, pytest-8.3.3
collected 24 items

tests/test_daily_stock.py::test_reconciliation_ok_within_tolerance        PASSED
tests/test_daily_stock.py::test_warning_requires_remarks                  PASSED
tests/test_daily_stock.py::test_duplicate_plant_and_date_rejected         PASSED
tests/test_daily_stock.py::test_unknown_plant_rejected                    PASSED
tests/test_daily_stock.py::test_negative_values_rejected                  PASSED
tests/test_fsa_constraints.py::test_end_date_before_start_date_rejected   PASSED
tests/test_fsa_constraints.py::test_valid_constraint_created              PASSED
tests/test_landed_cost.py::test_total_landed_cost_is_computed             PASSED
tests/test_landed_cost.py::test_negative_cost_rejected                    PASSED
tests/test_landed_cost.py::test_effective_to_before_effective_from_rejected PASSED
tests/test_master_data.py::test_duplicate_plant_code_rejected             PASSED
tests/test_master_data.py::test_alias_must_reference_existing_plant       PASSED
tests/test_master_data.py::test_duplicate_alias_rejected                  PASSED
tests/test_master_data.py::test_alias_static_route_not_shadowed_by_plant_id_route PASSED
tests/test_optimization.py::test_optimization_allocates_from_fsa_using_landed_cost PASSED
tests/test_optimization.py::test_market_topup_used_when_acq_cap_insufficient PASSED
tests/test_optimization.py::test_incomplete_data_when_no_landed_cost_and_no_fallback PASSED
tests/test_optimization.py::test_no_shortfall_returns_completed_with_no_allocation PASSED
tests/test_variable_cost_parser.py::test_parses_known_plant_and_ignores_ntpc PASSED
tests/test_variable_cost_parser.py::test_row_without_number_marked_not_confident PASSED
tests/test_variable_cost_parser.py::test_unknown_plant_ignored            PASSED
tests/test_variable_cost_parser.py::test_empty_pdf_marks_text_not_extracted PASSED
tests/test_variable_cost_upload.py::test_upload_parses_only_known_uprvunl_plant PASSED
tests/test_variable_cost_upload.py::test_duplicate_pdf_hash_rejected      PASSED

============================= 24 passed in 9.69s ==============================
```
RESULT: 24/24 PASSED

Note: pytest-asyncio emits a PytestDeprecationWarning about asyncio_default_fixture_loop_scope.
This is a library warning from pytest-asyncio 0.24.0; it does not affect any tests.

---

## 6. Docker, Migrations, Health, Swagger

| Check | Result | Notes |
|---|---|---|
| Docker Desktop | PASS | v29.2.1, started successfully |
| PostgreSQL container | PASS | codsp_postgres via docker compose up -d db |
| Alembic upgrade head | PASS | Migration e28cd7418010 (initial schema) applied |
| FastAPI app startup | PASS | uvicorn app.main:app --host 127.0.0.1 --port 8001 |
| Scheduler | PASS (disabled) | SCHEDULER_ENABLED=false, as expected |
| GET /docs | PASS | HTTP 200 - Swagger UI loads |
| GET /api/v1/health | PASS | HTTP 200 - {"status": "ok", "database": "ok"} |
| DB connection | PASS | Health endpoint confirms SELECT 1 succeeds |

---

## 7. Remaining Blockers

None - the backend runs cleanly end to end.

### Environmental note (not a code bug):
PyMuPDF==1.24.10 ships a Windows native DLL (pymupdf/_extra.pyd) that is blocked by
the Windows Application Control policy on this machine. The lazy-import fix means the
app starts regardless; the parser will gracefully mark uploaded PDFs as needs_review if
the DLL remains blocked. If the DLL issue is resolved (e.g. a newer VC++ runtime or a
policy exception), the parser will work transparently with no further code changes.

### Docker Desktop warm-up:
Docker Desktop requires 60-90 seconds to initialize its WSL2/Linux engine after OS login.
The docker compose up command will fail with "pipe not found" during that window; retry
after Docker Desktop shows as fully running in the system tray.

---

## 8. Summary of Files Changed

| File | Change |
|---|---|
| app/modules/documents/variable_cost_parser.py | Moved import fitz from module-level to inside extract_text_lines() |
| requirements.txt | Changed PyMuPDF==1.24.10 to PyMuPDF==1.23.26 |
| LOCAL_VERIFICATION_REPORT.md | Created (this file) |
