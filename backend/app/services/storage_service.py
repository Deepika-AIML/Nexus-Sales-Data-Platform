"""
Storage service: everything about getting an uploaded file safely onto
disk, and safely back off disk into a DataFrame.

Deliberately does ONLY file-level validation (spec section 3) — it never
looks at column names, nulls, duplicates, or "does this look like a sales
dataset". That analysis belongs to the profiling/mapping stages, which run
strictly after a successful upload.
"""
import os
import re
import uuid
from io import BytesIO

import pandas as pd

from app.core.config import get_settings
from app.core.exceptions import FileValidationError
from app.core.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

CANDIDATE_ENCODINGS = ("utf-8", "utf-8-sig", "cp1252", "latin1")


def sanitize_filename(filename: str) -> str:
    """Strips any path components and disallowed characters — prevents
    path traversal regardless of what the client sends as a filename."""
    base = os.path.basename(filename)
    base = re.sub(r"[^A-Za-z0-9._\-]", "_", base)
    return base[:200] if base else "upload.csv"


def validate_upload(filename: str, content: bytes) -> None:
    if not filename.lower().endswith(".csv"):
        raise FileValidationError("Unsupported file type. Please upload a CSV file.")

    if len(content) == 0:
        raise FileValidationError("The uploaded file is empty.")

    if len(content) > settings.UPLOAD_MAX_BYTES:
        raise FileValidationError(
            f"File exceeds the {settings.UPLOAD_MAX_MB} MB upload limit."
        )


def detect_encoding_and_read(content: bytes, nrows: int | None = None) -> tuple[pd.DataFrame, str]:
    """Tries a short, ordered list of common encodings. Raises
    FileValidationError with a clean message if none of them work — this is
    the ONLY case where an unreadable CSV is rejected at upload time.

    Note: cp1252/latin1 can decode ANY byte sequence (they're total mappings
    over all 256 byte values), so those encodings alone can't tell binary
    garbage apart from a real CSV — a corrupt/binary file will often
    "successfully" decode into a single nonsense header with zero data
    rows. A file with no data rows at all isn't something Nexus can
    profile or map, so that's treated as a file-level read failure here
    (distinct from "dirty" data, which is a later-stage concern) rather
    than accepted as a technically-parseable-but-empty upload."""
    last_error = None
    for enc in CANDIDATE_ENCODINGS:
        try:
            df = pd.read_csv(BytesIO(content), encoding=enc, nrows=nrows, on_bad_lines="error")
            if df.shape[1] < 1:
                raise ValueError("no columns parsed")
            if df.shape[0] < 1:
                raise ValueError("no data rows parsed")
            return df, enc
        except Exception as e:  # noqa: BLE001 — intentionally broad, we try several encodings
            last_error = e
            continue

    logger.warning("CSV read failed for all candidate encodings: %s", last_error)
    raise FileValidationError(
        "We couldn't read this CSV. Please verify that it is a valid CSV file."
    )


def save_raw_file(dataset_id: str, filename: str, content: bytes) -> str:
    os.makedirs(settings.RAW_DIR, exist_ok=True)
    safe_name = sanitize_filename(filename)
    stored_filename = f"{dataset_id}__{safe_name}"
    dest_path = os.path.join(settings.RAW_DIR, stored_filename)

    # dataset_id is a freshly generated UUID for every upload, so a
    # collision here would indicate a real bug — fail loudly rather than
    # silently overwriting a previous upload (spec section 3).
    if os.path.exists(dest_path):
        raise FileValidationError("A file with this identifier already exists. Please retry the upload.")

    with open(dest_path, "wb") as f:
        f.write(content)

    return stored_filename


def new_dataset_id() -> str:
    return str(uuid.uuid4())


def load_raw_dataframe(dataset_id: str, stored_filename: str, encoding: str) -> pd.DataFrame:
    path = os.path.join(settings.RAW_DIR, stored_filename)
    return pd.read_csv(path, encoding=encoding)
