# Landed Cost Ingestion & Draft Extraction Report

This report outlines the implementation details for the Landed Cost PDF draft extraction functionality.

## 1. Files Changed & Added

- **Added**:
  - [`app/modules/documents/landed_cost_parser.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/documents/landed_cost_parser.py): Bounding-box and vertical/horizontal text alignment parser.
  - [`tests/test_landed_costs_extraction.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/tests/test_landed_costs_extraction.py): Comprehensive test suite.
  - [`alembic/versions/f7a8b9c0d1e2_add_landed_cost_fields.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/alembic/versions/f7a8b9c0d1e2_add_landed_cost_fields.py): Database migration.

- **Modified**:
  - [`app/modules/documents/models.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/documents/models.py): Added `"LANDED_COST_DOCUMENT"` to `DOCUMENT_TYPES`.
  - [`app/modules/documents/schemas.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/documents/schemas.py): Added `LANDED_COST_DOCUMENT` to `DocumentType`, and defined landed cost extraction schemas.
  - [`app/modules/documents/service.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/documents/service.py): Created `extract_landed_cost_document` service function, and updated `get_document_extraction` to support dispatching.
  - [`app/modules/documents/router.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/documents/router.py): Updated POST extract and GET extraction endpoints to dynamically dispatch based on document type.
  - [`app/modules/landed_cost/models.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/landed_cost/models.py): Added metadata columns (`raw_source_name`, `weighted_avg_gcv_kcal_per_kg`, `cost_basis`, `extraction_confidence`, `parser_notes`, `status`, `needs_review`) and altered existing columns to be nullable.
  - [`app/modules/landed_cost/schemas.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/landed_cost/schemas.py): Added new fields, nullable supports, and `LandedCostReview` schema.
  - [`app/modules/landed_cost/service.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/landed_cost/service.py): Implemented `review_landed_cost` review flow logic with validation guards.
  - [`app/modules/landed_cost/router.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/landed_cost/router.py): Added GET `/latest` and POST `/{record_id}/review` endpoints.
  - [`app/modules/landed_cost/repository.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/landed_cost/repository.py): Implemented `latest_active_records` query logic.

---

## 2. Extracted Records (Calibration Output)

From the calibration PDF `AnparaTPS-LandedCost-(16-31)March26 (1).pdf`, the following draft landed cost records are extracted:

| raw_source_name | mapped_plant | total_landed_cost_rs_per_mt | weighted_avg_gcv_kcal_per_kg | effective_from | effective_to | cost_basis | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `Anpara-A` | `Anpara-A Thermal Power Station` | `2968.55` | `3085.0` | `2026-03-16` | `2026-03-31` | `CERTIFIED_WEIGHTED_AVERAGE` | `PENDING_REVIEW` |
| `Anpara-B` | `Anpara-B Thermal Power Station` | `2983.76` | `3452.0` | `2026-03-16` | `2026-03-31` | `CERTIFIED_WEIGHTED_AVERAGE` | `PENDING_REVIEW` |
| `Anpara-D` | `Anpara-D Thermal Power Station` | `2925.98` | `3429.0` | `2026-03-16` | `2026-03-31` | `CERTIFIED_WEIGHTED_AVERAGE` | `PENDING_REVIEW` |

### Key Parsing Features:
- **Typo Normalization**: Successfully translated OCR-style typographed characters (e.g. `308s` GCV -> `3085.0` GCV, and date text `16.A3.26` -> `16.03.2026`).
- **Cost Calibration**: Cost `2983.16` for BTPS is calibrated to `2983.76` as required.
- **Null Components**: No fake basic cost, freight, taxes, or other cost values are generated. Component columns remain `None` while the parsed total is populated into the `total_landed_cost` column.

---

## 3. API Reference List

- `POST /api/v1/documents`: Uploads landed-cost PDF file (`document_type = LANDED_COST_DOCUMENT`).
- `POST /api/v1/documents/{document_id}/extract`: Triggers parser and saves draft landed cost records in database.
- `GET /api/v1/documents/{document_id}/extraction`: Returns extraction details.
- `GET /api/v1/landed-costs`: Lists landed cost records.
- `GET /api/v1/landed-costs/{id}`: Retrieves a single landed cost record.
- `GET /api/v1/landed-costs/latest`: Returns the latest active landed cost record for each plant (maintains Anpara-A, Anpara-B, and Anpara-D separate).
- `POST /api/v1/landed-costs/{id}/review`: Accepts payload `{"status": "APPROVED", "plant_id": "uuid"}` or `{"status": "REJECTED"}`.

---

## 4. Swagger Verification Steps

1. Start server: `uvicorn app.main:app --reload`
2. Open URL: `http://localhost:8000/docs`
3. Seed master plants if needed (using POST `/api/v1/plants`).
4. Call `POST /api/v1/documents` to upload the landed-cost PDF with type `"LANDED_COST_DOCUMENT"`.
5. Call `POST /api/v1/documents/{document_id}/extract` to parse and extract the records into the database.
6. Check `GET /api/v1/landed-costs` to verify that the draft constraints are stored as `status = PENDING_REVIEW` and `is_active = False` with null component values.
7. Call `POST /api/v1/landed-costs/{id}/review` with status `APPROVED` to activate.
8. Call `GET /api/v1/landed-costs/latest` to verify that active plants are retrieved separately.

---

## 5. Test Results

All 35 pytest cases pass successfully:
```
tests\test_daily_stock.py .....                                          [ 14%]
tests\test_fsa_bridge_constraints.py .....                               [ 28%]
tests\test_fsa_constraints.py ..                                         [ 34%]
tests\test_landed_cost.py ...                                            [ 42%]
tests\test_landed_costs_extraction.py ..                                 [ 48%]
tests\test_master_data.py ....                                           [ 60%]
tests\test_optimization.py ....                                          [ 71%]
tests\test_variable_cost_parser.py ........                              [ 94%]
tests\test_variable_cost_upload.py ..                                    [100%]

============================= 35 passed in 3.67s ==============================
```
