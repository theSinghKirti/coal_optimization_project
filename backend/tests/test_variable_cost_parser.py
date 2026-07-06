"""Deterministic Variable Cost PDF parser tests (pure unit tests, no DB)."""

import fitz

from app.modules.documents.variable_cost_parser import (
    normalize_name,
    parse_variable_cost_pdf,
)


def _build_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text, fontsize=11)
    return doc.tobytes()


def test_parses_known_plant_and_ignores_ntpc():
    pdf_bytes = _build_pdf("Anpara-A    2.35\n" "NTPC Dadri                      3.10\n")
    tokens = {"anpara-a": "Anpara-A Thermal Power Station"}
    result = parse_variable_cost_pdf(pdf_bytes, tokens)

    assert result.text_extracted is True
    assert len(result.rows) == 1
    assert result.rows[0].source_plant_name == "Anpara-A"
    assert result.rows[0].variable_cost_per_unit == 2.35
    assert result.rows[0].confident is True


def test_row_without_number_marked_not_confident():
    pdf_bytes = _build_pdf("Anpara-A    Under Review\n")
    tokens = {"anpara-a": "Anpara-A Thermal Power Station"}
    result = parse_variable_cost_pdf(pdf_bytes, tokens)

    assert len(result.rows) == 1
    assert result.rows[0].confident is False
    assert result.rows[0].variable_cost_per_unit is None


def test_unknown_plant_ignored():
    pdf_bytes = _build_pdf("Some Random Private Plant     4.00\n")
    tokens = {"anpara-a": "Anpara-A Thermal Power Station"}
    result = parse_variable_cost_pdf(pdf_bytes, tokens)
    assert len(result.rows) == 0


def test_empty_pdf_marks_text_not_extracted():
    doc = fitz.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    result = parse_variable_cost_pdf(pdf_bytes, {"anpara-a": "Anpara-A"})
    assert result.text_extracted is False


def test_alias_normalization():
    # Test normalize_name utility directly
    assert normalize_name("OBRA-B") == "obrab"
    assert normalize_name("Obra B") == "obrab"
    assert normalize_name("Obra-B") == "obrab"
    assert normalize_name("Anpara - A") == "anparaa"
    assert normalize_name("Anpara-A") == "anparaa"
    assert normalize_name("JAWAHARPUR") == "jawaharpur"
    assert normalize_name("Parichha - Ext.") == "parichhaext"
    assert normalize_name("Harduaganj Ext. II TPS") == "harduaganjextiitps"

    # Test matching alias variations in parser
    pdf_bytes = _build_pdf(
        "31 OBRA-B 3.692\n"
        "Obra B 3.692\n"
        "22 JAWAHARPUR 4.091\n"
        "48 Anpara - A 2.786\n"
    )
    tokens = {
        "obra-b": "Obra-B Thermal Power Station",
        "jawaharpur": "Jawaharpur Thermal Power Station",
        "anpara - a": "Anpara-A Thermal Power Station",
    }
    result = parse_variable_cost_pdf(pdf_bytes, tokens)
    assert len(result.rows) == 4
    # All rows parsed confidently
    assert all(r.confident for r in result.rows)
    assert result.rows[0].source_plant_name == "OBRA-B"
    assert result.rows[0].variable_cost_per_unit == 3.692
    assert result.rows[2].source_plant_name == "JAWAHARPUR"
    assert result.rows[2].variable_cost_per_unit == 4.091


def test_date_range_extraction_from_header():
    pdf_bytes = _build_pdf(
        "UPSLDC Variable Cost Report\n"
        "Effective from 01-07-2026 to 15-07-2026\n"
        "12 Harduaganj 5.129\n"
    )
    tokens = {"harduaganj": "Harduaganj"}
    result = parse_variable_cost_pdf(pdf_bytes, tokens)
    assert len(result.rows) == 1
    assert result.rows[0].effective_from == "2026-07-01"
    assert result.rows[0].effective_to == "2026-07-15"
    assert result.rows[0].effective_date == "2026-07-01"  # stores effective_from


def test_parser_ignores_unrelated_generators():
    pdf_bytes = _build_pdf(
        "1 Kawas GPS (NAPM) 14.995\n"
        "12 Harduaganj 5.129\n"
        "14 Dadri (T) I 4.442\n"
        "22 JAWAHARPUR 4.091\n"
    )
    tokens = {
        "harduaganj": "Harduaganj",
        "jawaharpur": "Jawaharpur",
    }
    result = parse_variable_cost_pdf(pdf_bytes, tokens)
    assert len(result.rows) == 2
    assert {r.source_plant_name for r in result.rows} == {"Harduaganj", "JAWAHARPUR"}


def test_generic_ambiguous_names_flagged():
    pdf_bytes = _build_pdf(
        "12 Anpara 2.786\n"
        "31 Obra 3.692\n"
    )
    # Tokens only contain specific units, not generic base names
    tokens = {
        "anpara-a": "Anpara-A Thermal Power Station",
        "obra-b": "Obra-B Thermal Power Station",
    }
    result = parse_variable_cost_pdf(pdf_bytes, tokens)
    # The generic rows should not match exactly, but are flagged as relevant and needs_review
    assert len(result.rows) == 2
    assert all(not r.confident for r in result.rows)
    assert result.rows[0].source_plant_name == "Anpara"
    assert result.rows[0].matched_plant_token == ""


