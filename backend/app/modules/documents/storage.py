"""Local filesystem storage for uploaded documents (Version 1 storage backend)."""

import hashlib
import uuid
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()


def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def save_file(content: bytes, original_filename: str, subfolder: str = "") -> str:
    """Saves file content to the local document storage path and returns the stored path."""
    base_dir = Path(settings.document_storage_path) / subfolder
    base_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(original_filename).suffix or ".pdf"
    stored_name = f"{uuid.uuid4()}{suffix}"
    stored_path = base_dir / stored_name

    with open(stored_path, "wb") as f:
        f.write(content)

    return str(stored_path)
