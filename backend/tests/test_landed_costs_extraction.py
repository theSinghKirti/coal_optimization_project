import uuid
from datetime import date

from sqlalchemy import select

from app.modules.documents.landed_cost_parser import parse_landed_cost_pdf
from app.modules.landed_cost.models import LandedCost
from app.modules.master_data.models import Plant

REAL_PDF_PATH = (
    r"c:\Users\itisa\Desktop\UP_CODSP_backend\backend\test_data"
    r"\AnparaTPS-LandedCost-(16-31)March26 (1).pdf"
)


def test_landed_cost_parser_extraction():
    with open(REAL_PDF_PATH, "rb") as f:
        pdf_bytes = f.read()

    records, notes = parse_landed_cost_pdf(pdf_bytes)

    assert len(notes) == 0
    assert len(records) == 3

    # Anpara-A (ATPS)
    r_a = next(r for r in records if r.raw_source_name == "Anpara-A")
    assert r_a.total_landed_cost_rs_per_mt == 2968.55
    # Expect GCV to be None due to "308s" unconfident token
    assert r_a.weighted_avg_gcv_kcal_per_kg is None
    assert r_a.effective_from == date(2026, 3, 16)
    assert r_a.effective_to == date(2026, 3, 31)
    assert r_a.extraction_confidence == 0.0
    assert "Unconfident numeric token in GCV: '308s'" in r_a.parser_notes

    # Anpara-B (BTPS)
    r_b = next(r for r in records if r.raw_source_name == "Anpara-B")
    assert r_b.total_landed_cost_rs_per_mt == 2983.16  # Raw value, no digit edits/guessing!
    assert r_b.weighted_avg_gcv_kcal_per_kg == 3452.0
    assert r_b.effective_from == date(2026, 3, 16)
    assert r_b.effective_to == date(2026, 3, 31)
    assert r_b.extraction_confidence == 1.0

    # Anpara-D (DTPS)
    r_d = next(r for r in records if r.raw_source_name == "Anpara-D")
    assert r_d.total_landed_cost_rs_per_mt == 2925.98
    assert r_d.weighted_avg_gcv_kcal_per_kg == 3429.0
    assert r_d.effective_from == date(2026, 3, 16)
    assert r_d.effective_to == date(2026, 3, 31)
    assert r_d.extraction_confidence == 1.0


def test_landed_cost_integration_and_review(client, db_session):
    # Seed Anpara-A, B, D plants in DB
    p_a = Plant(plant_code="ANPARA-A", plant_name="Anpara-A Thermal Power Station")
    p_b = Plant(plant_code="ANPARA-B", plant_name="Anpara-B Thermal Power Station")
    p_d = Plant(plant_code="ANPARA-D", plant_name="Anpara-D Thermal Power Station")
    db_session.add_all([p_a, p_b, p_d])
    db_session.flush()

    plant_a_id = p_a.id
    plant_b_id = p_b.id
    plant_d_id = p_d.id

    with open(REAL_PDF_PATH, "rb") as f:
        pdf_bytes = f.read()

    # 1. Upload document
    resp_upload = client.post(
        "/api/v1/documents",
        data={"document_type": "LANDED_COST_DOCUMENT", "original_filename": "anpara_landed.pdf"},
        files={"file": ("anpara_landed.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp_upload.status_code == 201
    doc_id = resp_upload.json()["id"]

    # 2. Trigger extraction
    resp_extract = client.post(f"/api/v1/documents/{doc_id}/extract")
    assert resp_extract.status_code == 201
    
    data = resp_extract.json()
    assert data["document_id"] == doc_id
    assert len(data["parsed_records"]) == 3

    # Check database records
    stmt = select(LandedCost).where(LandedCost.document_id == uuid.UUID(doc_id))
    db_records = list(db_session.execute(stmt).scalars().all())
    assert len(db_records) == 3

    # Ensure separate plant mappings & needs_review flag on ATPS due to GCV typo
    rec_a = next(r for r in db_records if r.raw_source_name == "Anpara-A")
    assert rec_a.plant_id == plant_a_id
    assert rec_a.needs_review is True
    assert rec_a.extraction_confidence == 0.0

    rec_b = next(r for r in db_records if r.raw_source_name == "Anpara-B")
    assert rec_b.plant_id == plant_b_id
    assert rec_b.needs_review is False
    assert rec_b.extraction_confidence == 1.0

    rec_d = next(r for r in db_records if r.raw_source_name == "Anpara-D")
    assert rec_d.plant_id == plant_d_id
    assert rec_d.needs_review is False
    assert rec_d.extraction_confidence == 1.0

    # 3. Test review approval validation guards
    # Case A: Approve valid record (rec_a)
    resp_approve = client.post(
        f"/api/v1/landed-costs/{rec_a.id}/review",
        json={"status": "APPROVED"}
    )
    assert resp_approve.status_code == 200
    assert resp_approve.json()["status"] == "APPROVED"
    assert resp_approve.json()["is_active"] is True

    # Case B: Create invalid record to test non-positive cost rejection
    invalid_cost_rec = LandedCost(
        plant_id=plant_b_id,
        document_id=uuid.UUID(doc_id),
        total_landed_cost=-10.0,
        effective_from=date(2026, 3, 16),
        effective_to=date(2026, 3, 31),
        status="PENDING_REVIEW",
        is_active=False
    )
    db_session.add(invalid_cost_rec)
    db_session.flush()

    resp_approve_invalid = client.post(
        f"/api/v1/landed-costs/{invalid_cost_rec.id}/review",
        json={"status": "APPROVED"}
    )
    assert resp_approve_invalid.status_code == 422
    assert "positive" in resp_approve_invalid.json()["error"]["message"].lower()

    # Case C: Create invalid record to test backward date range rejection
    invalid_dates_rec = LandedCost(
        plant_id=plant_b_id,
        document_id=uuid.UUID(doc_id),
        total_landed_cost=100.0,
        effective_from=date(2026, 3, 31),
        effective_to=date(2026, 3, 16),
        status="PENDING_REVIEW",
        is_active=False
    )
    db_session.add(invalid_dates_rec)
    db_session.flush()

    resp_approve_dates = client.post(
        f"/api/v1/landed-costs/{invalid_dates_rec.id}/review",
        json={"status": "APPROVED"}
    )
    assert resp_approve_dates.status_code == 422
    assert "effective_from" in resp_approve_dates.json()["error"]["message"].lower()


    # 4. Check GET /latest only returns active records and groups them separately
    resp_latest = client.get("/api/v1/landed-costs/latest")
    assert resp_latest.status_code == 200
    latest_list = resp_latest.json()
    
    # Only approved Anpara-A should be in latest active records list
    assert len(latest_list) == 1
    assert latest_list[0]["plant_id"] == str(plant_a_id)
