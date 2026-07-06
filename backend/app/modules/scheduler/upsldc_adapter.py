"""Scheduler-ready adapter for the UPSLDC Variable Cost PDF source.

Responsible only for: checking the source, discovering unseen PDF links, and
downloading up to `UPSLDC_MAX_PDFS_PER_RUN` of them. Parsing and persistence
are delegated to the Documents module's deterministic Variable Cost parser,
so this adapter contains no parsing/AI logic of its own.

Must degrade gracefully: if the UPSLDC site is unreachable, this returns a
structured failure result instead of raising, so the scheduler (and its
callers) never crash a run because an external website is down.
"""

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.documents import repository as documents_repository
from app.modules.documents import service as documents_service

settings = get_settings()

_PDF_LINK_PATTERN = re.compile(r'href=["\']([^"\']+\.pdf)["\']', re.IGNORECASE)


@dataclass
class IngestionResult:
    source_reachable: bool
    discovered_links: list[str] = field(default_factory=list)
    downloaded: int = 0
    skipped_duplicates: int = 0
    failed_downloads: int = 0
    documents_created: list[str] = field(default_factory=list)  # document ids as str
    notes: list[str] = field(default_factory=list)


def discover_pdf_links(source_url: str, timeout_seconds: float = 15.0) -> list[str]:
    """Fetches the UPSLDC page and extracts .pdf links. Never raises."""
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        response = client.get(source_url)
        response.raise_for_status()
        html = response.text

    links = _PDF_LINK_PATTERN.findall(html)
    absolute_links = [urljoin(source_url, link) for link in links]
    # De-duplicate while preserving order (assume page lists newest first).
    seen = set()
    ordered_unique = []
    for link in absolute_links:
        if link not in seen:
            seen.add(link)
            ordered_unique.append(link)
    return ordered_unique


def run_ingestion(db: Session) -> IngestionResult:
    result = IngestionResult(source_reachable=True)

    try:
        links = discover_pdf_links(settings.upsldc_source_url)
    except Exception as exc:  # noqa: BLE001 - must never crash the scheduler
        result.source_reachable = False
        result.notes.append(f"UPSLDC source unreachable: {exc}")
        return result

    result.discovered_links = links
    if not links:
        result.notes.append("No PDF links found on the UPSLDC source page.")
        return result

    candidate_links = links[: settings.upsldc_max_pdfs_per_run]

    for link in candidate_links:
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.get(link)
                response.raise_for_status()
                content = response.content
        except Exception as exc:  # noqa: BLE001
            result.failed_downloads += 1
            result.notes.append(f"Failed to download {link}: {exc}")
            continue

        filename = link.rsplit("/", 1)[-1] or "variable_cost.pdf"

        from app.modules.documents.storage import compute_sha256

        file_hash = compute_sha256(content)
        if documents_repository.get_document_by_hash(db, file_hash):
            result.skipped_duplicates += 1
            continue

        try:
            document, _rows, _parser_notes = documents_service.upload_and_parse_variable_cost_pdf(
                db, content=content, original_filename=filename
            )
            db.commit()
            result.downloaded += 1
            result.documents_created.append(str(document.id))
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            result.failed_downloads += 1
            result.notes.append(f"Failed to ingest {link}: {exc}")

    return result
