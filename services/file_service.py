from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path
from uuid import uuid4

from werkzeug.utils import secure_filename


MAX_LOG_BYTES = 2 * 1024 * 1024
MAX_ZIP_BYTES = 20 * 1024 * 1024
MAX_EXTRACTED_BYTES = 40 * 1024 * 1024
ALLOWED_LOG_EXTENSIONS = {".log", ".txt"}


def create_investigation_dir(root: Path) -> Path:
    path = root / f"INV-{uuid4().hex[:8].upper()}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def save_log(upload, destination: Path) -> str:
    filename = secure_filename(upload.filename or "")
    if not filename or Path(filename).suffix.lower() not in ALLOWED_LOG_EXTENSIONS:
        raise ValueError("This file type is not supported. Logs must be .log or .txt files.")
    if upload.content_length and upload.content_length > MAX_LOG_BYTES:
        raise ValueError("The uploaded log is too large. The limit is 2 MB.")
    target = destination / filename
    upload.save(target)
    if target.stat().st_size > MAX_LOG_BYTES:
        target.unlink(missing_ok=True)
        raise ValueError("The uploaded log is too large. The limit is 2 MB.")
    return filename


def _safe_member_path(root: Path, member_name: str) -> Path:
    target = (root / member_name).resolve()
    if root.resolve() not in target.parents and target != root.resolve():
        raise ValueError("The uploaded ZIP contains an unsafe path.")
    return target


def save_project_zip(upload, destination: Path) -> str:
    filename = secure_filename(upload.filename or "")
    if not filename or Path(filename).suffix.lower() != ".zip":
        raise ValueError("This file type is not supported. Project source must be a .zip file.")
    if upload.content_length and upload.content_length > MAX_ZIP_BYTES:
        raise ValueError("The uploaded ZIP is too large. The limit is 20 MB.")
    archive_path = destination / filename
    upload.save(archive_path)
    if archive_path.stat().st_size > MAX_ZIP_BYTES:
        archive_path.unlink(missing_ok=True)
        raise ValueError("The uploaded ZIP is too large. The limit is 20 MB.")

    extract_path = destination / "source"
    extract_path.mkdir()
    extracted_bytes = 0
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                target = _safe_member_path(extract_path, member.filename)
                extracted_bytes += member.file_size
                if extracted_bytes > MAX_EXTRACTED_BYTES:
                    raise ValueError("The uploaded ZIP expands beyond the 40 MB safety limit.")
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
    except (zipfile.BadZipFile, OSError, ValueError) as error:
        shutil.rmtree(extract_path, ignore_errors=True)
        if isinstance(error, ValueError):
            raise
        raise ValueError("The uploaded ZIP could not be processed safely.") from error
    finally:
        archive_path.unlink(missing_ok=True)
    return filename


def cleanup_investigation(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)