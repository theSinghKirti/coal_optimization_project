# FSA & Bridge Linkage Ingestion & Draft Extraction Report

This report outlines the implementation details for the FSA and Bridge Linkage PDF draft extraction functionality.

## 1. Files Changed & Added

- **Added**:
  - [`app/modules/documents/fsa_bridge_parser.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/documents/fsa_bridge_parser.py): Contains the deterministic, coordinate-based PDF text parser.
  - [`tests/test_fsa_bridge_constraints.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/tests/test_fsa_bridge_constraints.py): Tests the parser, API endpoints, validations, and mapping flows.
  - [`alembic/versions/7d4944f5f4ac_add_fsa_bridge_fields.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/alembic/versions/7d4944f5f4ac_add_fsa_bridge_fields.py): Database migration script.

- **Modified**:
  - [`app/modules/documents/models.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/documents/models.py): Added `"FSA_BRIDGE_LINKAGE_DOCUMENT"` to `DOCUMENT_TYPES`.
  - [`app/modules/documents/schemas.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/documents/schemas.py): Added `FSA_BRIDGE_LINKAGE_DOCUMENT` to `DocumentType`, and added extraction schemas.
  - [`app/modules/documents/service.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/documents/service.py): Added `extract_fsa_bridge_document` and `get_document_extraction` service functions.
  - [`app/modules/documents/router.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/documents/router.py): Added POST extract and GET extraction endpoints.
  - [`app/modules/constraints/models.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/constraints/models.py): Modified `FSAConstraint` columns to allow nullable fields and store draft metadata. Renamed the `coal_company` relationship to `coal_company_rel` to prevent shadowing.
  - [`app/modules/constraints/schemas.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/constraints/schemas.py): Added support for new columns in read and create schemas, and created `FSAConstraintReview`.
  - [`app/modules/constraints/service.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/constraints/service.py): Refactored `update_constraint` to support nullable dates, and implemented `review_constraint` logic.
  - [`app/modules/constraints/router.py`](file:///c:/Users/itisa/Desktop/UP_CODSP_backend/backend/app/modules/constraints/router.py): Added POST review endpoint.

---

## 2. Database Migration Details

The migration `7d4944f5f4ac_add_fsa_bridge_fields` updates the `fsa_constraints` table:
- Adds columns:
  - `fiscal_year` (`VARCHAR(32)`)
  - `raw_source_name` (`VARCHAR(255)`)
  - `coal_company` (`VARCHAR(255)`)
  - `quantity_lac_mt` (`NUMERIC(16, 4)`)
  - `quantity_mt` (`NUMERIC(16, 3)`)
  - `valid_to` (`DATE`)
  - `remarks` (`VARCHAR(2000)`)
  - `extraction_confidence` (`NUMERIC(5, 2)`)
  - `parser_notes` (`VARCHAR(2000)`)
  - `status` (`VARCHAR(32)`, defaults to `"PENDING_REVIEW"`)
- Alters existing fields (`plant_id`, `annual_contract_quantity_mt`, `contract_start_date`, and `contract_end_date`) to be nullable to support incomplete draft extractions.

---

## 3. Supported PDF Table Layout

The parser segments the table horizontally by grouping PDF word bounding boxes that share similar vertical coordinates (Y0 center values, within a 3.0 point tolerance) and sorting them left-to-right (by X0).
It separates columns using deterministic X-coordinate boundaries:
- **FSA side**:
  - `Plant`: `X0 < 140`
  - `Coal Company`: `140 <= X0 < 220`
  - `ACQ (Lac MT)`: `220 <= X0 < 310`
- **Bridge Linkage side**:
  - `Plant`: `310 <= X0 < 450`
  - `Coal Company`: `450 <= X0 < 520`
  - `Bridge Linkage Qty. (Lac MT)`: `520 <= X0 < 570`
  - `Remarks`: `X0 >= 570`

---

## 4. Parser Rules

- **Grand Total Rows**: Skip lines where `fsa_plant` is exactly `"Total"` (case-insensitive).
- **FSA/Bridge Total Rows**: Skip individual sub-total items containing the word `"Total"` (e.g. `"Anpara Total"`), but process the opposite side if it has non-total data.
- **Parent Plant Name Propagation**: If a row has quantities/coal company but the plant name is empty, it inherits the plant name from the closest previous non-total row in that column.
- **Lac MT Conversion**: `1 Lac MT` is converted to `100,000 MT`.
- **Date Extraction**: Extract date string matching `"Valid till DD.MM.YYYY"` or `"Valid till DD-MM-YYYY"` in `Remarks` to store as `valid_to`.

---

## 5. Fields Extracted

- `fiscal_year`: e.g. `"2026-27"` (extracted from PDF header)
- `raw_source_name`: raw plant name exactly as written in the PDF cell (e.g. `"Anpara"`, `"Harduaganj Extn-II"`)
- `coal_company`: e.g. `"NCL"`, `"SECL"`, `"CCL"`
- `constraint_type`: `"FSA"` or `"BRIDGE_LINKAGE"`
- `quantity_lac_mt`: quantity in Lac MT
- `quantity_mt`: quantity in MT (converted)
- `valid_to`: date object when parsed from remarks, otherwise `None`
- `remarks`: Remarks cell text
- `document_id`: UUID of the source document
- `extraction_confidence`: `1.0` if successfully mapped to database master plant, `0.0` otherwise.
- `parser_notes`: lists reasons if confidence is `0.0` (e.g. `"Unresolved or ambiguous plant name: 'Anpara'"`)
- `status`: defaults to `"PENDING_REVIEW"`

---

## 6. Validation Rules

- **Duplicate Hash Protection**: The existing SHA-256 hash check ensures a PDF with the same content cannot be uploaded twice.
- **Quantity Non-Negativity**: Validations reject negative quantities.
- **End Date Validation**: When start and end dates are both present, end date cannot be earlier than start date.
- **Review Pre-requisite**: Approving a constraint requires that its `plant_id` is successfully mapped/provided, raising a `ValidationFailedError` (422) if not.
- **Active Record Scope**: Only records that are `APPROVED` (which sets `is_active = True`) will be visible/used in optimization. Draft constraints (`status = PENDING_REVIEW` or `REJECTED`) are marked `is_active = False`.

---

## 7. Review Flow

All parsed rows are loaded into `fsa_constraints` with `status = "PENDING_REVIEW"` and `is_active = False`.
A manual reviewer can approve or reject each draft using `POST /api/v1/fsa-constraints/{id}/review`:
- **APPROVED**: sets `status = "APPROVED"`, `is_active = True` and links to the confirmed/resolved `plant_id`.
- **REJECTED**: sets `status = "REJECTED"`, `is_active = False`.

---

## 8. Swagger Verification Steps

1. Launch application: `uvicorn app.main:app --reload`
2. Open documentation: `http://localhost:8000/docs`
3. Upload document:
   - Call `POST /api/v1/documents`
   - Select `file` (a select-text PDF file) and specify `document_type = "FSA_BRIDGE_LINKAGE_DOCUMENT"`
   - Execute to retrieve the `id` (e.g. `doc_id`)
4. Trigger extraction:
   - Call `POST /api/v1/documents/{doc_id}/extract`
   - Verify the parsed records and notes are returned
5. View extraction status:
   - Call `GET /api/v1/documents/{doc_id}/extraction`
6. Review constraint:
   - Call `POST /api/v1/fsa-constraints/{id}/review` with payload `{"status": "APPROVED", "plant_id": "<valid-plant-uuid>"}`

---

## 9. Test Results

All 33 test cases pass successfully:
- Unit tests verify the parser correctly parses the table layout, ignores total rows, converts quantities, and extracts dates.
- Integration tests assert exact alias resolving, ambiguous row review statuses, and duplicate SHA-256 hash rejections.
- Legacy variable cost tests remain unaffected.

```
tests\test_daily_stock.py .....                                          [ 15%]
tests\test_fsa_bridge_constraints.py .....                               [ 30%]
tests\test_fsa_constraints.py ..                                         [ 36%]
tests\test_landed_cost.py ...                                            [ 45%]
tests\test_master_data.py ....                                           [ 57%]
tests\test_optimization.py ....                                          [ 69%]
tests\test_variable_cost_parser.py ........                              [ 93%]
tests\test_variable_cost_upload.py ..                                    [100%]

============================= 33 passed in 2.96s ==============================
```

---

## 10. Known Limitations

- **Image/Scanned PDFs**: Only deterministic, selectable-text layouts are supported. Scanned, unreadable, or image-only documents will result in no extracted records and will be marked as `needs_review` with appropriate parser notes. OCR and AI-assisted extraction are out of scope.
