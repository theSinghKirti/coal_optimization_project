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


@dataclass
class ParsedRow:
    source_plant_name: str
    raw_line: str
    variable_cost_per_unit: float | None
    effective_date: str | None  # ISO date string, or None
    matched_plant_token: str
    confident: bool
    reason: str | None = None


@dataclass
class ParseResult:
    rows: list[ParsedRow] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    text_extracted: bool = True


def extract_text_lines(pdf_bytes: bytes) -> list[str]:
    """Extract selectable text lines from every page using PyMuPDF only."""
    import fitz  # PyMuPDF – lazy import so a missing/blocked DLL doesn't crash startup

    lines: list[str] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            text = page.get_text("text")
            for raw_line in text.splitlines():
                stripped = raw_line.strip()
                if stripped:
                    lines.append(stripped)
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

    for line in lines:
        line_lower = line.lower()

        if _looks_non_uprvunl(line_lower):
            continue  # explicitly excluded, never stored

        matched_token = None
        for token in known_plant_tokens:
            if token in line_lower:
                matched_token = token
                break

        if not matched_token:
            continue  # not a plant row we recognize; ignore silently

        numbers = _extract_numbers(line)
        effective_date = _extract_date(line)

        if not numbers:
            result.rows.append(
                ParsedRow(
                    source_plant_name=known_plant_tokens[matched_token],
                    raw_line=line,
                    variable_cost_per_unit=None,
                    effective_date=effective_date,
                    matched_plant_token=matched_token,
                    confident=False,
                    reason="Plant name matched but no numeric Variable Cost value found on the line.",
                )
            )
            continue

        # Heuristic: the Variable Cost figure is typically the last standalone
        # number on the row (preceding numbers are often plant/unit codes).
        variable_cost = numbers[-1]
        confident = True
        reason = None
        if len(numbers) > 1 and variable_cost > 50:
            # Variable Cost in Rs/kWh is normally a small decimal; a large
            # trailing number suggests we picked up a serial/code instead.
            confident = False
            reason = "Multiple numeric tokens on the line; trailing value looks atypical for Rs/kWh."

        result.rows.append(
            ParsedRow(
                source_plant_name=known_plant_tokens[matched_token],
                raw_line=line,
                variable_cost_per_unit=variable_cost,
                effective_date=effective_date,
                matched_plant_token=matched_token,
                confident=confident,
                reason=reason,
            )
        )

    if not result.rows:
        result.notes.append(
            "No UPRVUNL plant rows were recognized. Check that Plant/PlantAlias master data "
            "covers the plant names used in this PDF revision."
        )

    return result
