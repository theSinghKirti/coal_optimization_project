import re
from dataclasses import dataclass
from datetime import date

import fitz


@dataclass
class ExtractedConstraint:
    constraint_type: str
    raw_source_name: str
    coal_company: str | None
    quantity_lac_mt: float
    quantity_mt: float
    valid_to: date | None
    remarks: str | None
    extraction_confidence: float
    parser_notes: str | None

def normalize_name(name: str) -> str:
    """Normalize names by lowercasing and stripping all non-alphanumeric characters."""
    val = name.lower()
    return re.sub(r"[^a-z0-9]", "", val)

def extract_valid_to(remarks: str) -> date | None:
    if not remarks:
        return None
    # Matches "Valid till DD.MM.YYYY" or "Valid till DD-MM-YYYY"
    match = re.search(r"Valid\s+till\s+(\d{1,2})[-./](\d{1,2})[-./](\d{2,4})", remarks, re.IGNORECASE)
    if not match:
        return None
    day, month, year = match.groups()
    if len(year) == 2:
        year = f"20{year}"
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None

def is_total_string(val: str) -> bool:
    if not val:
        return False
    return "total" in val.lower()

def parse_fsa_bridge_pdf(pdf_bytes: bytes) -> tuple[str | None, list[ExtractedConstraint], list[str]]:
    notes = []
    records: list[ExtractedConstraint] = []
    fiscal_year = None

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        notes.append(f"Failed to open PDF with PyMuPDF: {e}")
        return None, [], notes

    if len(doc) == 0:
        notes.append("PDF contains no pages.")
        return None, [], notes

    page = doc[0]
    words = page.get_text("words")

    if not words:
        notes.append("No selectable text words found in the PDF.")
        return None, [], notes

    # Group words by Y coordinate
    y_tolerance = 3.0
    words_sorted = sorted(words, key=lambda w: (w[1], w[0]))
    
    lines = []
    current_line = []
    last_y0 = None

    for w in words_sorted:
        x0, y0, x1, y1, word, block_no, line_no, word_no = w
        if last_y0 is None:
            last_y0 = y0
            current_line.append(w)
        elif abs(y0 - last_y0) <= y_tolerance:
            current_line.append(w)
        else:
            current_line.sort(key=lambda x: x[0])
            lines.append(current_line)
            current_line = [w]
            last_y0 = y0

    if current_line:
        current_line.sort(key=lambda x: x[0])
        lines.append(current_line)

    # 1. Search for Fiscal Year in the text
    full_text = page.get_text("text")
    fy_match = re.search(r"FY\s*(\d{4}-\d{2,4})", full_text, re.IGNORECASE)
    if fy_match:
        fiscal_year = fy_match.group(1).strip()
    else:
        notes.append("Could not find Fiscal Year (FY) in PDF header.")

    current_fsa_plant = None
    current_bridge_plant = None

    for line in lines:

        # Filter columns using coordinates
        fsa_plant_words = []
        fsa_cc_words = []
        fsa_qty_words = []
        bridge_plant_words = []
        bridge_cc_words = []
        bridge_qty_words = []
        bridge_remarks_words = []

        for w in line:
            x0, y0, x1, y1, word, block_no, line_no, word_no = w
            if x0 < 140:
                fsa_plant_words.append(word)
            elif 140 <= x0 < 220:
                fsa_cc_words.append(word)
            elif 220 <= x0 < 310:
                fsa_qty_words.append(word)
            elif 310 <= x0 < 450:
                bridge_plant_words.append(word)
            elif 450 <= x0 < 520:
                bridge_cc_words.append(word)
            elif 520 <= x0 < 570:
                bridge_qty_words.append(word)
            else:
                bridge_remarks_words.append(word)

        fsa_plant = " ".join(fsa_plant_words).strip() or None
        fsa_cc = " ".join(fsa_cc_words).strip() or None
        fsa_qty_str = " ".join(fsa_qty_words).strip() or None

        bridge_plant = " ".join(bridge_plant_words).strip() or None
        bridge_cc = " ".join(bridge_cc_words).strip() or None
        bridge_qty_str = " ".join(bridge_qty_words).strip() or None
        bridge_remarks = " ".join(bridge_remarks_words).strip() or None

        if fsa_plant and fsa_plant.lower() == "total":
            continue

        # Update running parent plants
        if fsa_plant and not is_total_string(fsa_plant):
            current_fsa_plant = fsa_plant
        if bridge_plant and not is_total_string(bridge_plant):

            current_bridge_plant = bridge_plant

        # Process FSA Side
        if fsa_qty_str:
            # Check if quantity is negative
            try:
                raw_qty_str = fsa_qty_str.replace(",", "")
                qty_lac = float(raw_qty_str)
                qty_mt = qty_lac * 100000.0

                if not is_total_string(fsa_plant):
                    plant_name = fsa_plant or current_fsa_plant
                    if plant_name:
                        records.append(ExtractedConstraint(
                            constraint_type="FSA",
                            raw_source_name=plant_name,
                            coal_company=fsa_cc,
                            quantity_lac_mt=qty_lac,
                            quantity_mt=qty_mt,
                            valid_to=None,
                            remarks=None,
                            extraction_confidence=1.0,  # will adjust in service based on mapping
                            parser_notes=None
                        ))
            except ValueError:
                pass

        # Process Bridge Side
        if bridge_qty_str:
            try:
                raw_qty_str = bridge_qty_str.replace(",", "")
                qty_lac = float(raw_qty_str)
                qty_mt = qty_lac * 100000.0

                if not is_total_string(bridge_plant):
                    plant_name = bridge_plant or current_bridge_plant
                    if plant_name:
                        valid_to = extract_valid_to(bridge_remarks)
                        records.append(ExtractedConstraint(
                            constraint_type="BRIDGE_LINKAGE",
                            raw_source_name=plant_name,
                            coal_company=bridge_cc,
                            quantity_lac_mt=qty_lac,
                            quantity_mt=qty_mt,
                            valid_to=valid_to,
                            remarks=bridge_remarks,
                            extraction_confidence=1.0,
                            parser_notes=None
                        ))
            except ValueError:
                pass

    return fiscal_year, records, notes
