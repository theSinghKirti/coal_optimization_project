import uuid
from datetime import date

from app.modules.constraints.models import FSAConstraint
from app.modules.documents.fsa_bridge_parser import extract_valid_to, parse_fsa_bridge_pdf
from app.modules.documents.models import Document

REAL_PDF_PATH = (
    r"C:\Users\itisa\.gemini\antigravity-ide\brain\f83dca8e-b65c-4715-b8ef-3ce97fdf15f7"
    r"\media__1783324612932.pdf"
)



def test_parser_extracts_correct_rows_and_converts():
    # 1. Verify parsing of real calibration PDF layout
    with open(REAL_PDF_PATH, "rb") as f:
        pdf_bytes = f.read()

    fy, records, notes = parse_fsa_bridge_pdf(pdf_bytes)

    assert fy == "2026-27"
    assert len(notes) == 0

    # Ensure total rows are ignored: total extracted should be 15 rows
    # (7 FSA rows, 8 Bridge Linkage rows)
    assert len(records) == 15

    # Check FSA records
    fsa_recs = [r for r in records if r.constraint_type == "FSA"]
    assert len(fsa_recs) == 7
    # Anpara NCL 118.64
    assert fsa_recs[0].raw_source_name == "Anpara"
    assert fsa_recs[0].coal_company == "NCL"
    assert fsa_recs[0].quantity_lac_mt == 118.64
    assert fsa_recs[0].quantity_mt == 11864000.0  # Lac MT converts correctly to MT

    # Check Bridge Linkage records and validity date extraction
    bridge_recs = [r for r in records if r.constraint_type == "BRIDGE_LINKAGE"]
    assert len(bridge_recs) == 8
    # Harduaganj Extn-II CCL 12.33 Valid till 12.08.2026
    assert bridge_recs[0].raw_source_name == "Harduaganj Extn-II"
    assert bridge_recs[0].coal_company == "CCL"
    assert bridge_recs[0].quantity_lac_mt == 12.33
    assert bridge_recs[0].quantity_mt == 1233000.0
    assert bridge_recs[0].valid_to == date(2026, 8, 12)  # Extracted validity date correctly


def test_extract_valid_to_utility():
    assert extract_valid_to("Bridge Linkage Valid till 12.08.2026") == date(2026, 8, 12)
    assert extract_valid_to("Valid till 05-12-2027") == date(2027, 12, 5)
    assert extract_valid_to("No validity date") is None


def test_integration_plant_mapping_and_needs_review(client, db_session):
    # Setup canonical plants
    # Let's seed "Harduaganj Extn-II" and "Jawaharpur"
    resp_plant1 = client.post(
        "/api/v1/plants",
        json={"plant_code": "HG_EXT_2", "plant_name": "Harduaganj Extn-II"},
    )

    assert resp_plant1.status_code == 201
    plant1_id = resp_plant1.json()["id"]

    # Do NOT seed "Anpara" to test ambiguous mapping
    # Upload the PDF document first
    with open(REAL_PDF_PATH, "rb") as f:
        pdf_bytes = f.read()

    resp_upload = client.post(
        "/api/v1/documents",
        data={"document_type": "FSA_BRIDGE_LINKAGE_DOCUMENT", "original_filename": "matrix.pdf"},
        files={"file": ("matrix.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp_upload.status_code == 201
    doc_id = resp_upload.json()["id"]

    # Trigger extraction
    resp_extract = client.post(f"/api/v1/documents/{doc_id}/extract")
    assert resp_extract.status_code == 201
    data = resp_extract.json()
    assert data["document_id"] == doc_id
    assert len(data["parsed_records"]) == 15

    # Check document review status in database
    doc = db_session.get(Document, uuid.UUID(doc_id))
    # Since "Anpara" is ambiguous (not in master data), the document needs review!
    assert doc.needs_review is True
    assert doc.review_status == "needs_review"

    # Verify extracted records in DB
    constraints = db_session.query(FSAConstraint).filter(FSAConstraint.document_id == uuid.UUID(doc_id)).all()
    assert len(constraints) == 15

    # Harduaganj Extn-II should be mapped to plant1_id
    h_ext_recs = [c for c in constraints if c.raw_source_name == "Harduaganj Extn-II"]
    assert len(h_ext_recs) > 0
    assert str(h_ext_recs[0].plant_id) == plant1_id
    assert h_ext_recs[0].extraction_confidence == 1.0

    # Anpara should be unmapped (plant_id is None) and flagged with low confidence
    anpara_recs = [c for c in constraints if c.raw_source_name == "Anpara"]
    assert len(anpara_recs) > 0
    assert anpara_recs[0].plant_id is None
    assert anpara_recs[0].extraction_confidence == 0.0
    assert "Unresolved or ambiguous plant name" in anpara_recs[0].parser_notes
    assert anpara_recs[0].status == "PENDING_REVIEW"
    assert anpara_recs[0].is_active is False


def test_review_endpoint_approved_and_rejected(client, db_session):
    # Setup canonical plants
    resp_plant = client.post(
        "/api/v1/plants",
        json={"plant_code": "ANPARA_CANONICAL", "plant_name": "Anpara Station"},
    )

    plant_id = resp_plant.json()["id"]

    # Create a real document in DB to satisfy foreign key
    doc = Document(
        document_type="FSA_BRIDGE_LINKAGE_DOCUMENT",
        original_filename="dummy.pdf",
        storage_path="/tmp/dummy.pdf",
        sha256_hash="dummy_hash_123"
    )
    db_session.add(doc)
    db_session.flush()
    doc_id = doc.id

    # Create a draft constraint record manually in the DB to test review flow on unmapped record
    draft = FSAConstraint(
        constraint_type="FSA",
        annual_contract_quantity_mt=500000,
        status="PENDING_REVIEW",
        is_active=False,
        plant_id=None,
        document_id=doc_id
    )
    db_session.add(draft)
    db_session.flush()
    constraint_id = str(draft.id)


    # 1. Approve without providing plant_id should fail because it was created without plant_id
    resp_fail = client.post(f"/api/v1/fsa-constraints/{constraint_id}/review", json={"status": "APPROVED"})
    assert resp_fail.status_code == 422

    # 2. Try to approve when quantity is negative
    draft.annual_contract_quantity_mt = -100
    db_session.flush()
    resp_neg = client.post(
        f"/api/v1/fsa-constraints/{constraint_id}/review",
        json={"status": "APPROVED", "plant_id": plant_id},
    )
    assert resp_neg.status_code == 422
    draft.annual_contract_quantity_mt = 500000
    db_session.flush()

    # 3. Try to approve when document_id is None
    draft.document_id = None
    db_session.flush()
    resp_nodoc = client.post(
        f"/api/v1/fsa-constraints/{constraint_id}/review",
        json={"status": "APPROVED", "plant_id": plant_id},
    )
    assert resp_nodoc.status_code == 422
    draft.document_id = doc_id
    db_session.flush()

    # 4. Try to approve when constraint_type is invalid
    draft.constraint_type = "INVALID_TYPE"
    db_session.flush()
    resp_invtype = client.post(
        f"/api/v1/fsa-constraints/{constraint_id}/review",
        json={"status": "APPROVED", "plant_id": plant_id},
    )
    assert resp_invtype.status_code == 422
    draft.constraint_type = "FSA"
    db_session.flush()

    # 5. Approve with valid plant_id
    resp_approve = client.post(
        f"/api/v1/fsa-constraints/{constraint_id}/review",
        json={"status": "APPROVED", "plant_id": plant_id},
    )
    assert resp_approve.status_code == 200
    assert resp_approve.json()["status"] == "APPROVED"
    assert resp_approve.json()["is_active"] is True
    assert resp_approve.json()["plant_id"] == plant_id

    # 6. Try to approve when status is already APPROVED (must fail because it's not currently PENDING_REVIEW)
    resp_already = client.post(
        f"/api/v1/fsa-constraints/{constraint_id}/review",
        json={"status": "APPROVED", "plant_id": plant_id},
    )
    assert resp_already.status_code == 422

    # 7. Verify unmapped/pending records remain inactive and are excluded from active queries
    # Add a pending record
    pending = FSAConstraint(
        constraint_type="FSA",
        annual_contract_quantity_mt=300000,
        status="PENDING_REVIEW",
        is_active=False,
        plant_id=uuid.UUID(plant_id),
        contract_start_date=date(2026, 1, 1),
        contract_end_date=date(2026, 12, 31)
    )
    db_session.add(pending)
    db_session.flush()

    from app.modules.constraints.repository import list_active_for_plant
    active_recs = list_active_for_plant(db_session, uuid.UUID(plant_id), as_of=date(2026, 6, 1))
    assert pending.id not in [r.id for r in active_recs]


def test_duplicate_document_hash_rejection(client):
    with open(REAL_PDF_PATH, "rb") as f:
        pdf_bytes = f.read()

    # Reset/clear previous documents in DB to avoid collisions if already exists
    # Actually, conftest rolls back, but let's upload under unique circumstances
    # First upload
    resp_first = client.post(
        "/api/v1/documents",
        data={"document_type": "FSA_BRIDGE_LINKAGE_DOCUMENT", "original_filename": "matrix_first.pdf"},
        files={"file": ("matrix_first.pdf", pdf_bytes, "application/pdf")},
    )
    # If it already exists in the persistent DB, it might return 409, otherwise 201
    if resp_first.status_code == 201:
        # Second upload of the same content should trigger ConflictError (409)
        resp_second = client.post(
            "/api/v1/documents",
            data={"document_type": "FSA_BRIDGE_LINKAGE_DOCUMENT", "original_filename": "matrix_second.pdf"},
            files={"file": ("matrix_second.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp_second.status_code == 409
    else:
        assert resp_first.status_code == 409
