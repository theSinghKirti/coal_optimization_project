"""Deterministic, rule-based parser for UPSLDC Variable Cost PDFs.

Design constraints (per project scope):
- PyMuPDF (fitz) only. No OCR, no AI/LLM extraction.
- Only rows that can be matched to a known UPRVUNL plant (via Plant master
  data or a Plant Alias) are considered "confident". Everything else is
  either ignored (clearly a non-UPRVUNL/NTPC/private/IPP row) or kept and
  flagged `needs_review` (looks like a plant row but could not be parsed
  with full confidence).

Because UPSLDC PDF layouts vary release to release, this parser works on the
selectable text stream rather than assuming a fixed column grid. It looks,
line by line, for a known plant name/alias followed by the first plausible
numeric value on that line (the Variable Cost figure, in Rs/kWh). If a date
in DD-MM-YYYY or DD.MM.YYYY form is present on the same line it is captured
as the effective date; otherwise effective_date is left null rather than
guessed, per the "store effective dates only when confidently extracted" rule.

Non-UPRVUNL generators (NTPC/private/IPP) are recognized by keyword and
skipped outright — they are never stored, confident or otherwise.
"""

import re
from dataclasses import dataclass, field

_NUMBER_PATTERN = re.compile(r"(\d+(?:,\d{3})*(?:\.\d+)?)")
_DATE_PATTERN = re.compile(r"(\d{1,2})[-.](\d{1,2})[-.](\d{2,4})")

# Keywords that identify rows which are clearly NOT UPRVUNL and must be ignored
# outright, even if they contain a numeric value.
NON_UPRVUNL_KEYWORDS = (
    "ntpc",
    "private",
    "ipp",
    "npgc",
    "captive",
    "central sector",
)


def normalize_name(name: str) -> str:
    """Normalize names by lowercasing and stripping all non-alphanumeric characters."""
    val = name.lower()
    return re.sub(r"[^a-z0-9]", "", val)


@dataclass
class ParsedRow:
    source_plant_name: str
    raw_line: str
    variable_cost_per_unit: float | None
    effective_date: str | None  # ISO date string, or None (will store effective_from)
    matched_plant_token: str
    confident: bool
    reason: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None


@dataclass
class ParseResult:
    rows: list[ParsedRow] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    text_extracted: bool = True


def extract_text_lines(pdf_bytes: bytes) -> list[str]:
    """Extract selectable text lines from every page using PyMuPDF only."""
    import fitz  # PyMuPDF – lazy import so a missing/blocked DLL doesn't crash startup

    raw_lines: list[str] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            text = page.get_text("text")
            for raw_line in text.splitlines():
                stripped = raw_line.strip()
                if stripped:
                    raw_lines.append(stripped)

    # Reconstruct lines where columns are split vertically
    lines: list[str] = []
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]
        if i + 2 < len(raw_lines):
            item1 = raw_lines[i]
            item2 = raw_lines[i + 1]
            item3 = raw_lines[i + 2]

            # Check if item1 is a serial number (integer) and item3 is a number (float/int)
            is_item1_int = re.match(r"^\d+$", item1)
            is_item3_number = re.match(r"^\d+(?:\.\d+)?$", item3)

            if is_item1_int and is_item3_number:
                lines.append(f"{item1} {item2} {item3}")
                i += 3
                continue

        lines.append(line)
        i += 1

    return lines


def _looks_non_uprvunl(line_lower: str) -> bool:
    return any(keyword in line_lower for keyword in NON_UPRVUNL_KEYWORDS)


def _extract_date(line: str) -> str | None:
    match = _DATE_PATTERN.search(line)
    if not match:
        return None
    day, month, year = match.groups()
    if len(year) == 2:
        year = f"20{year}"
    try:
        day_i, month_i, year_i = int(day), int(month), int(year)
        if not (1 <= day_i <= 31 and 1 <= month_i <= 12):
            return None
        return f"{year_i:04d}-{month_i:02d}-{day_i:02d}"
    except ValueError:
        return None


def _extract_numbers(line: str) -> list[float]:
    numbers = []
    for raw in _NUMBER_PATTERN.findall(line):
        try:
            numbers.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return numbers


def parse_line_components(line: str) -> tuple[str, float | None]:
    """Extracts (raw_station_name, variable_cost) from a line.

    Handles lines with or without a leading serial number.
    """
    line = line.strip()
    if not line:
        return "", None

    # Find all numeric values
    numbers = _extract_numbers(line)
    if not numbers:
        # If no numbers, the entire line is the station name, cost is None
        return line, None

    # The cost is the last number on the line
    cost = numbers[-1]

    # Find where the cost string starts in the raw line
    # Match trailing float/number
    cost_pattern = re.compile(r"\s+\d+(?:\.\d+)?$")
    match = cost_pattern.search(line)
    if match:
        remainder = line[:match.start()].strip()
    else:
        # Fallback split
        parts = line.split()
        remainder = " ".join(parts[:-1])

    # Now, check if there is a leading serial number
    # If the remainder starts with an integer followed by space, we strip it
    serial_match = re.match(r"^\d+\s+(.*)$", remainder)
    if serial_match:
        remainder = serial_match.group(1).strip()

    return remainder, cost


def parse_variable_cost_pdf(pdf_bytes: bytes, known_plant_tokens: dict[str, str]) -> ParseResult:
    """Parse a Variable Cost PDF deterministically.

    known_plant_tokens: mapping of {normalized_alias_or_name_lower: canonical_display_name}
    built from Plant + PlantAlias master data. Only lines that contain one of
    these tokens are treated as UPRVUNL rows.
    """
    result = ParseResult()

    try:
        lines = extract_text_lines(pdf_bytes)
    except Exception as exc:  # noqa: BLE001 - deterministic parser must never crash the request
        result.text_extracted = False
        result.notes.append(f"Failed to extract selectable text via PyMuPDF: {exc}")
        return result

    if not lines:
        result.text_extracted = False
        result.notes.append("No selectable text found in PDF (may be a scanned/image-only document).")
        return result

    # Extract date range from the entire text
    full_text = "\n".join(lines)
    date_range_pattern = re.compile(
        r"effective\s+from\s+(\d{1,2})[-./](\d{1,2})[-./](\d{2,4})\s+to\s+(\d{1,2})[-./](\d{1,2})[-./](\d{2,4})",
        re.IGNORECASE
    )
    date_match = date_range_pattern.search(full_text)
    effective_from = None
    effective_to = None
    if date_match:
        d1, m1, y1, d2, m2, y2 = date_match.groups()
        if len(y1) == 2:
            y1 = f"20{y1}"
        if len(y2) == 2:
            y2 = f"20{y2}"
        try:
            effective_from = f"{int(y1):04d}-{int(m1):02d}-{int(d1):02d}"
            effective_to = f"{int(y2):04d}-{int(m2):02d}-{int(d2):02d}"
        except ValueError:
            pass

    for line in lines:
        line_lower = line.lower()

        if _looks_non_uprvunl(line_lower):
            continue  # explicitly excluded, never stored

        raw_station_name, variable_cost = parse_line_components(line)
        if not raw_station_name:
            continue

        # Exact matching on normalized name
        norm_station = normalize_name(raw_station_name)
        matched_orig_token = None

        # Look for exact normalized match
        for tok in known_plant_tokens:
            if normalize_name(tok) == norm_station:
                matched_orig_token = tok
                break

        row_effective_date = effective_from if effective_from else _extract_date(line)

        if not matched_orig_token:
            # If it's not a recognized UPRVUNL row, check if it's potentially relevant.
            # Relevant rows contain keywords: anpara, obra, harduaganj, parichha, panki, jawaharpur.
            # If so, we save it as not confident (needs_review = True).
            relevance_keywords = {"anpara", "obra", "harduaganj", "parichha", "panki", "jawaharpur"}
            is_relevant = any(kw in norm_station for kw in relevance_keywords)
            if is_relevant:
                result.rows.append(
                    ParsedRow(
                        source_plant_name=raw_station_name,
                        raw_line=line,
                        variable_cost_per_unit=variable_cost,
                        effective_date=row_effective_date,
                        matched_plant_token="",
                        confident=False,
                        reason="Unrecognized or ambiguous plant/unit name.",
                        effective_from=effective_from,
                        effective_to=effective_to,
                    )
                )
            continue

        # Determine confidence
        confident = True
        reason = None
        if variable_cost is None:
            confident = False
            reason = "No numeric Variable Cost value found on the line."

        result.rows.append(
            ParsedRow(
                source_plant_name=raw_station_name,
                raw_line=line,
                variable_cost_per_unit=variable_cost,
                effective_date=row_effective_date,
                matched_plant_token=matched_orig_token,
                confident=confident,
                reason=reason,
                effective_from=effective_from,
                effective_to=effective_to,
            )
        )

    if not result.rows:
        result.notes.append(
            "No UPRVUNL plant rows were recognized. Check that Plant/PlantAlias master data "
            "covers the plant names used in this PDF revision."
        )

    return result
