# CODSP — Real UPSLDC Variable Cost Parser Calibration Report

This report documents the resolution of the plant mapping integrity fix, ensuring that each raw PDF station row maps to exactly one distinct canonical plant/unit record without incorrect collapsing.

---

## 1. Mapped UPRVUNL Plant & Cost Records

After reprocessing the uploaded PDF (ID: `cb4f1555-457f-44f7-823b-11f36c83acc1`), the following 13 distinct unit-level records are stored in the database:

| Raw PDF Name | Canonical Plant/Unit | Plant ID | VC Value | Status |
| :--- | :--- | :--- | :---: | :--- |
| Harduaganj | Harduaganj Thermal Power Station | `97374af8-ad35-4097-adcb-f5d9f43bb710` | 5.1290 | Confident (`needs_review=False`) |
| JAWAHARPUR | Jawaharpur Thermal Power Station | `44280dd2-b200-4bfa-a6b7-1e05e3385d71` | 4.0910 | Confident (`needs_review=False`) |
| Harduaganj Ext. | Harduaganj Ext. Thermal Power Station | `13b056c9-ca6f-408d-96cf-8c94d92e2a1f` | 3.9900 | Confident (`needs_review=False`) |
| Parichha - Ext. | Parichha - Ext. Thermal Power Station | `90543552-9a3a-46dc-b8e8-3d6cf78cf708` | 3.8670 | Confident (`needs_review=False`) |
| Parichha - Ext. Stage - II | Parichha - Ext. Stage - II Thermal Power Station | `593affaa-4cf2-4f48-8284-21d7ae41ca1a` | 3.8670 | Confident (`needs_review=False`) |
| Harduaganj Ext. II TPS | Harduaganj Ext. II Thermal Power Station | `71aa862f-064c-41d5-8316-66553070379c` | 3.8140 | Confident (`needs_review=False`) |
| OBRA-B | Obra-B Thermal Power Station | `029a9ea8-d85d-4990-ba62-9cebbd6e5428` | 3.6920 | Confident (`needs_review=False`) |
| Panki | Panki Thermal Power Station | `3f44843a-032f-40fe-a082-461dd97fe906` | 3.3120 | Confident (`needs_review=False`) |
| Anpara - A | Anpara-A Thermal Power Station | `a49095ca-217a-403a-a817-46c8c01c768c` | 2.7860 | Confident (`needs_review=False`) |
| OBRA-C | Obra-C Thermal Power Station | `cc02b8a4-e554-449f-9ea5-766745c5fe33` | 2.7450 | Confident (`needs_review=False`) |
| Anpara-C | Anpara-C Thermal Power Station | `f7ff1eae-f0ee-4e31-804b-605cdca82577` | 2.5970 | Confident (`needs_review=False`) |
| Anpara - B | Anpara-B Thermal Power Station | `f7fc18a0-b0d8-485c-8970-47416efa70b8` | 2.4260 | Confident (`needs_review=False`) |
| Anpara-D | Anpara-D Thermal Power Station | `6c8faeb0-8a01-4e56-8a03-89850fcdd5db` | 2.2480 | Confident (`needs_review=False`) |

*Integrity Check:* Every successfully parsed raw PDF row is saved with its own distinct `plant_id`. No two different unit labels share the same `plant_id`.

---

## 2. Unsafe Aliases Removed/Deactivated

To prevent ambiguous matching, the following aliases were removed from the seeded master data aliases:
* `"Anpara"`, `"Anpara TPS"`, `"M/s Anpara"` (would cause generic collapses)
* `"Obra"`, `"Obra TPS"`
* `"Parichha"`, `"Parichha TPS"`

Any raw rows matching these names directly will not match any exact canonical alias, avoiding silent generic mapping.

---

## 3. Ambiguous Rows Marked for Review

Any row containing keywords of interest (`anpara`, `obra`, `parichha`, etc.) but lacking a distinct unit-level suffix (making it ambiguous and not matching any exact database alias) is successfully saved with `confident=False` (`needs_review=True`) and `plant_id=None`.
* Verification test: `test_generic_ambiguous_names_flagged` verifies this behavior.

---

## 4. Rows Intentionally Ignored

All unrelated private IPPs and NTPC stations (e.g. Kawas GPS, Anta, Auraiya, Dadri, Solapur TPS, Jhajjar, Rosa, BEPL, etc.) are bypassed cleanly during text extraction parsing.

---

## 5. Verification Tests

All **28 tests** (including unit-level mapping integrity, duplicate alias conflicts, and ambiguous generic name rejection) pass successfully:
```
============================= 28 passed in 2.31s ==============================
```

Code style check via ruff is completely clean:
```
python -m ruff check .
All checks passed!
```
---

## 6. Swagger / API Verification

1. Start your local FastAPI backend server.
2. Open Swagger UI in your browser: `http://127.0.0.1:8000/docs`
3. Execute `GET /api/v1/variable-cost/latest`.
   - Returns all **13 unit-level records separately** with their individual plant IDs (verifying they are not collapsed).
4. Execute `GET /api/v1/variable-cost`.
   - Returns the complete history of **13 parsed rows** with exactly preserved raw PDF names (e.g. `Anpara - A`).
5. Run `python -m app.seed` twice in your console. The seed script verifies idempotency and prints `[skip]` for all existing master records.
