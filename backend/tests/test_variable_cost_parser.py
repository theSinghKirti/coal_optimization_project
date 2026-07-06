"""Deterministic Variable Cost PDF parser tests (pure unit tests, no DB)."""

import fitz

from app.modules.documents.variable_cost_parser import parse_variable_cost_pdf


def _build_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text, fontsize=11)
    return doc.tobytes()


def test_parses_known_plant_and_ignores_ntpc():
    pdf_bytes = _build_pdf("Anpara Thermal Power Station    2.35\n" "NTPC Dadri                      3.10\n")
    tokens = {"anpara thermal power station": "Anpara Thermal Power Station"}
    result = parse_variable_cost_pdf(pdf_bytes, tokens)

    assert result.text_extracted is True
    assert len(result.rows) == 1
    assert result.rows[0].source_plant_name == "Anpara Thermal Power Station"
    assert result.rows[0].variable_cost_per_unit == 2.35
    assert result.rows[0].confident is True


def test_row_without_number_marked_not_confident():
    pdf_bytes = _build_pdf("Anpara Thermal Power Station    Under Review\n")
    tokens = {"anpara thermal power station": "Anpara Thermal Power Station"}
    result = parse_variable_cost_pdf(pdf_bytes, tokens)

    assert len(result.rows) == 1
    assert result.rows[0].confident is False
    assert result.rows[0].variable_cost_per_unit is None


def test_unknown_plant_ignored():
    pdf_bytes = _build_pdf("Some Random Private Plant     4.00\n")
    tokens = {"anpara thermal power station": "Anpara Thermal Power Station"}
    result = parse_variable_cost_pdf(pdf_bytes, tokens)
    assert len(result.rows) == 0


def test_empty_pdf_marks_text_not_extracted():
    doc = fitz.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    result = parse_variable_cost_pdf(pdf_bytes, {"anpara": "Anpara"})
    assert result.text_extracted is False
