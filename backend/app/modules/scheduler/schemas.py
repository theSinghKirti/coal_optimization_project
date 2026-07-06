from pydantic import BaseModel


class IngestionRunResult(BaseModel):
    source_reachable: bool
    discovered_links: int
    downloaded: int
    skipped_duplicates: int
    failed_downloads: int
    documents_created: list[str]
    notes: list[str]
