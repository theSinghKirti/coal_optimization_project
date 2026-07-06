"""End-to-end Variable Cost PDF upload tests through the API."""

import fitz


def _build_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text, fontsize=11)
    return doc.tobytes()


def test_upload_parses_only_known_uprvunl_plant(client):
    client.post("/api/v1/plants", json={"plant_code": "VC01", "plant_name": "Anpara Thermal Power Station"})

    pdf_bytes = _build_pdf_bytes("Anpara Thermal Power Station    2.40\nNTPC Dadri    3.05\n")
    resp = client.post(
        "/api/v1/variable-cost/upload",
        files={"file": ("vc.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["parsed_rows"]) == 1
    assert body["parsed_rows"][0]["source_plant_name"] == "Anpara Thermal Power Station"
    assert body["rows_needing_review"] == 0


def test_duplicate_pdf_hash_rejected(client):
    pdf_bytes = _build_pdf_bytes("Anpara Thermal Power Station    2.40\n")
    client.post(
        "/api/v1/plants",
        json={"plant_code": "VC02", "plant_name": "Anpara Thermal Power Station 2"},
    )

    first = client.post(
        "/api/v1/variable-cost/upload", files={"file": ("vc.pdf", pdf_bytes, "application/pdf")}
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/variable-cost/upload", files={"file": ("vc2.pdf", pdf_bytes, "application/pdf")}
    )
    assert second.status_code == 409
