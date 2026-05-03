import os
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile


UPLOAD_ROOT = Path("uploads")


async def save_file(file: UploadFile, destination_path: str) -> str:
    """Save an uploaded file to local storage and return stored path."""
    # Replace with S3 implementation by changing this service only
    base = UPLOAD_ROOT / Path(destination_path)
    base.mkdir(parents=True, exist_ok=True)

    safe_name = Path(file.filename or "document.bin").name
    stored_name = f"{uuid4().hex}_{safe_name}"
    full_path = base / stored_name

    data = await file.read()
    full_path.write_bytes(data)
    await file.seek(0)

    return str(full_path.as_posix())


async def delete_file(file_path: str) -> bool:
    """Delete a stored file if it exists."""
    path = Path(file_path)
    if not path.exists():
        return False
    path.unlink(missing_ok=True)
    return True


async def get_file_url(file_path: str) -> str:
    """Return a local URL-like path for the stored file."""
    normalized = file_path.replace("\\", "/")
    return f"/{normalized.lstrip('/')}"


async def save_bytes_file(file_bytes: bytes, relative_file_path: str) -> str:
    """Persist raw bytes to local storage and return stored path."""
    target = UPLOAD_ROOT / Path(relative_file_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(file_bytes)
    return str(target.as_posix())
