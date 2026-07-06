import re
from dataclasses import dataclass
from datetime import date

import fitz


@dataclass
class ExtractedLandedCost:
    raw_source_name: str
    total_landed_cost_rs_per_mt: float | None
    weighted_avg_gcv_kcal_per_kg: float | None
    effective_from: date | None
    effective_to: date | None
    extraction_confidence: float
    parser_notes: str | None


def parse_date_part(d_str: str) -> date | None:
    # Match something like 16.03.26, 16.A3.26, 31.03.26
    # Let's normalize A3 -> 03
    d_str_clean = d_str.replace("A3", "03").replace("a3", "03")
    match = re.search(r"(\d{2})[.\-\/](\d{2})[.\-\/](\d{2,4})", d_str_clean)
    if not match:
        return None
    day = int(match.group(1))
    month = int(match.group(2))
    year_str = match.group(3)
    if len(year_str) == 2:
        year = 2000 + int(year_str)
    else:
        year = int(year_str)
    try:
        return date(year, month, day)
    except Exception:
        return None


def parse_landed_cost_pdf(pdf_bytes: bytes) -> tuple[list[ExtractedLandedCost], list[str]]:
    notes = []
    records = []
    
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        notes.append(f"Failed to open PDF document: {e}")
        return [], notes

    if len(doc) < 2:
        notes.append("PDF must have at least 2 pages (Page 2 contains summary certificate).")
        return [], notes

    page = doc[1]  # Page 2 is index 1
    words = page.get_text("words")
    if not words:
        notes.append("Page 2 does not contain selectable text (may be scanned).")
        return [], notes

    # Group words by Y coordinate to construct lines
    lines_dict = {}
    for w in words:
        x0, y0, x1, y1, word, block_no, line_no, word_no = w
        # Y center
        yc = (y0 + y1) / 2.0
        # Group by Y within 4.0 points tolerance
        found = False
        for y_key in lines_dict.keys():
            if abs(y_key - yc) < 4.0:
                lines_dict[y_key].append(w)
                found = True
                break
        if not found:
            lines_dict[yc] = [w]

    # Sort lines by Y coordinate
    sorted_y = sorted(lines_dict.keys())
    lines = []
    for y in sorted_y:
        # Sort words on this line by X coordinate
        line_words = sorted(lines_dict[y], key=lambda item: item[0])
        lines.append(line_words)

    # 1. Extract Period
    effective_from = None
    effective_to = None
    period_pattern = re.compile(r"(\d{2})[.\-\/][0-9A-Za-z]{2}[.\-\/]\d{2,4}")

    for line in lines:
        line_text = " ".join([w[4] for w in line])
        if "to" in line_text and period_pattern.search(line_text):
            matches = period_pattern.findall(line_text)
            if len(matches) >= 2:
                # Find the words matching the dates
                date_words = []
                for w in line:
                    word_val = w[4]
                    if period_pattern.search(word_val) or word_val == "to":
                        date_words.append(word_val)
                # date_words might contain e.g. ["(16.A3.26", "to", "31.03.26)"]
                # Let's clean and parse
                clean_dates = []
                for dw in date_words:
                    dw_clean = dw.strip("()[],; ")
                    if period_pattern.match(dw_clean):
                        clean_dates.append(dw_clean)
                if len(clean_dates) >= 2:
                    effective_from = parse_date_part(clean_dates[0])
                    effective_to = parse_date_part(clean_dates[1])
                    break

    if not effective_from or not effective_to:
        notes.append("Could not extract effective period (e.g. 16.03.26 to 31.03.26) from Page 2.")

    # 2. Extract Landed Cost and GCV rows
    cost_values = {"ATPS": None, "BTPS": None, "DTPS": None}
    gcv_values = {"ATPS": None, "BTPS": None, "DTPS": None}
    unconfident_tokens = {"ATPS": [], "BTPS": [], "DTPS": []}

    def assign_to_band(x0: float, val_str: str, target_dict: dict, label: str):
        if 330 <= x0 < 400:
            band_key = "ATPS"
        elif 400 <= x0 < 480:
            band_key = "BTPS"
        elif 480 <= x0 < 560:
            band_key = "DTPS"
        else:
            return

        # Rule 1: Remove harmless formatting only: commas, spaces, currency symbols
        val_clean = val_str.replace(",", "").replace(" ", "").replace("Rs", "").strip()

        # Rule 2 & 3: Never change digits or guess. Ensure token is confidently numeric.
        if not re.match(r"^[\+\-]?\d+(\.\d+)?$", val_clean):
            unconfident_tokens[band_key].append(f"Unconfident numeric token in {label}: '{val_str}'")
            return

        try:
            val_float = float(val_clean)
            target_dict[band_key] = val_float
        except ValueError:
            unconfident_tokens[band_key].append(f"Unconfident numeric token in {label}: '{val_str}'")

    for idx, line in enumerate(lines):
        line_text = " ".join([w[4] for w in line]).lower()
        is_landed_cost = (
            "weighted" in line_text
            and "landed" in line_text
            and ("mt" in line_text or "rs. /mt" in line_text)
        )
        if is_landed_cost:
            for w in line:
                x0, y0, x1, y1, word, block_no, line_no, word_no = w
                assign_to_band(x0, word, cost_values, "Landed Cost")
        elif "weighted" in line_text and "gcv" in line_text and "oil" not in line_text:
            for next_idx in [idx + 1, idx + 2]:
                if next_idx < len(lines):
                    next_line = lines[next_idx]
                    next_line_text = " ".join([w[4] for w in next_line]).lower()
                    if "kcal/kg" in next_line_text or "kg" in next_line_text:
                        for w in next_line:
                            x0, y0, x1, y1, word, block_no, line_no, word_no = w
                            assign_to_band(x0, word, gcv_values, "GCV")



    # Validate that we got values
    sources = [
        ("ATPS", "Anpara-A"),
        ("BTPS", "Anpara-B"),
        ("DTPS", "Anpara-D")
    ]

    for band_key, raw_name in sources:
        cost = cost_values.get(band_key)
        gcv = gcv_values.get(band_key)
        
        row_notes = []
        confidence = 1.0
        
        if unconfident_tokens[band_key]:
            row_notes.extend(unconfident_tokens[band_key])
            confidence = 0.0

        if cost is None:
            if not any("Landed Cost" in token for token in unconfident_tokens[band_key]):
                row_notes.append(f"Missing Landed Cost of Coal for {band_key}.")
            confidence = 0.0
        if gcv is None:
            if not any("GCV" in token for token in unconfident_tokens[band_key]):
                row_notes.append(f"Missing GCV of Coal for {band_key}.")
            confidence = 0.0
        if not effective_from or not effective_to:
            row_notes.append("Missing effective period dates.")
            confidence = 0.0

        parser_notes_str = "; ".join(row_notes) if row_notes else None


        records.append(ExtractedLandedCost(
            raw_source_name=raw_name,
            total_landed_cost_rs_per_mt=cost,
            weighted_avg_gcv_kcal_per_kg=gcv,
            effective_from=effective_from,
            effective_to=effective_to,
            extraction_confidence=confidence,
            parser_notes=parser_notes_str
        ))

    return records, notes
