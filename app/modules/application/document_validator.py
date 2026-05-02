import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from uuid import UUID

from PIL import Image
from PyPDF2 import PdfReader
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.application_document import ApplicationDocument
from app.models.document_validation_log import DocumentValidationLog


@dataclass
class RuleResult:
    check_type: str
    result: str
    message: str


@dataclass
class ValidationResult:
    status: str
    message: str
    checks: List[RuleResult]


def _status_priority(checks: List[RuleResult]) -> tuple[str, str]:
    invalid = [c for c in checks if c.result == "FAIL"]
    suspicious = [c for c in checks if c.result == "WARNING"]
    if invalid:
        return "INVALID", invalid[0].message
    if suspicious:
        return "SUSPICIOUS", suspicious[0].message
    return "VALID", "All validation checks passed."


def _extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    chunks: List[str] = []
    for page in reader.pages:
        chunks.append(page.extract_text() or "")
    return " ".join(chunks).strip()


async def run_document_validation(document_id: UUID, db: AsyncSession) -> ValidationResult:
    """Run validation checks and persist rule-level logs and final status."""
    doc = (
        await db.execute(
            select(ApplicationDocument).where(ApplicationDocument.id == document_id)
        )
    ).scalars().first()
    if not doc:
        return ValidationResult(status="INVALID", message="Document not found.", checks=[])

    checks: List[RuleResult] = []
    path = Path(doc.file_path)
    if not path.exists():
        checks.append(RuleResult("FILE_FORMAT_CHECK", "FAIL", "File appears corrupted or unreadable."))
        doc.validation_status = "INVALID"
        doc.validation_message = "File appears corrupted or unreadable."
        doc.validated_at = datetime.now(timezone.utc)
        db.add(
            DocumentValidationLog(
                document_id=doc.id,
                application_id=doc.application_id,
                check_type="FILE_FORMAT_CHECK",
                result="FAIL",
                message="File appears corrupted or unreadable.",
            )
        )
        await db.commit()
        return ValidationResult(status="INVALID", message=doc.validation_message, checks=checks)

    file_bytes = path.read_bytes()
    file_size_kb = len(file_bytes) // 1024
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    doc.file_hash = file_hash
    doc.file_size_kb = file_size_kb

    extracted_text = ""

    # 1) File format check
    try:
        if doc.mime_type == "application/pdf":
            extracted_text = _extract_pdf_text(path)
        elif doc.mime_type in {"image/jpeg", "image/png", "image/tiff"}:
            with Image.open(path) as image:
                image.verify()
        checks.append(RuleResult("FILE_FORMAT_CHECK", "PASS", "File format is valid."))
    except Exception:
        checks.append(
            RuleResult(
                "FILE_FORMAT_CHECK",
                "FAIL",
                "File appears corrupted or unreadable.",
            )
        )

    # 2) File size check
    if file_size_kb > 2048:
        checks.append(RuleResult("FILE_SIZE_CHECK", "FAIL", "File exceeds 2MB limit."))
    else:
        checks.append(RuleResult("FILE_SIZE_CHECK", "PASS", "File size is within limit."))

    # 3) Blank document check (PDF only)
    if doc.mime_type == "application/pdf":
        if len(extracted_text) < 50:
            checks.append(
                RuleResult(
                    "BLANK_DOCUMENT_CHECK",
                    "WARNING",
                    "Document appears blank or has very little content.",
                )
            )
        else:
            checks.append(RuleResult("BLANK_DOCUMENT_CHECK", "PASS", "Sufficient textual content found."))

    # 4) Duplicate document check
    duplicate = (
        await db.execute(
            select(ApplicationDocument.id).where(
                and_(
                    ApplicationDocument.application_id == doc.application_id,
                    ApplicationDocument.file_hash == file_hash,
                    ApplicationDocument.id != doc.id,
                )
            )
        )
    ).first()
    if duplicate:
        checks.append(RuleResult("DUPLICATE_DOCUMENT_CHECK", "FAIL", "Duplicate file detected."))
    else:
        checks.append(RuleResult("DUPLICATE_DOCUMENT_CHECK", "PASS", "No duplicate detected."))

    # 5) Photo resolution check
    if doc.document_type == "PHOTO":
        try:
            with Image.open(path) as image:
                width, height = image.size
            if width < 200 or height < 200:
                checks.append(
                    RuleResult(
                        "PHOTO_VALIDATION",
                        "FAIL",
                        "Photo resolution too low. Minimum 200x200 pixels.",
                    )
                )
            else:
                checks.append(RuleResult("PHOTO_VALIDATION", "PASS", "Photo resolution is acceptable."))
        except Exception:
            checks.append(RuleResult("PHOTO_VALIDATION", "FAIL", "File appears corrupted or unreadable."))

    # 5a) General Image Quality Check (JPEG/TIFF)
    if doc.mime_type in {"image/jpeg", "image/tiff"}:
        try:
            with Image.open(path) as image:
                width, height = image.size
                dpi = image.info.get("dpi")
                
                if doc.mime_type == "image/jpeg":
                    if width < 640 or height < 480:
                        checks.append(RuleResult("IMAGE_QUALITY_CHECK", "FAIL", "JPEG resolution too low. Minimum 640x480 pixels."))
                    else:
                        checks.append(RuleResult("IMAGE_QUALITY_CHECK", "PASS", "JPEG resolution is acceptable."))
                
                elif doc.mime_type == "image/tiff":
                    if dpi and (dpi[0] < 600 or dpi[1] < 600):
                        checks.append(RuleResult("IMAGE_QUALITY_CHECK", "FAIL", f"TIFF DPI too low ({dpi[0]}x{dpi[1]}). Minimum 600x600 dpi."))
                    elif not dpi:
                        checks.append(RuleResult("IMAGE_QUALITY_CHECK", "WARNING", "Could not detect DPI in TIFF document."))
                    else:
                        checks.append(RuleResult("IMAGE_QUALITY_CHECK", "PASS", "TIFF DPI is acceptable."))
        except Exception as e:
            checks.append(RuleResult("IMAGE_QUALITY_CHECK", "FAIL", f"AI Validation Error: Could not process image file ({str(e)}). File may be corrupted."))

    # 6) Document type mismatch (basic)
    if doc.document_type == "AADHAR":
        if doc.mime_type in {"image/jpeg", "image/png"}:
            checks.append(
                RuleResult(
                    "DOCUMENT_TYPE_MISMATCH",
                    "WARNING",
                    "Uploaded file may not match selected document type. Please verify.",
                )
            )
        elif doc.mime_type == "application/pdf" and len(extracted_text) == 0:
            checks.append(
                RuleResult(
                    "DOCUMENT_TYPE_MISMATCH",
                    "WARNING",
                    "Uploaded file may not match selected document type. Please verify.",
                )
            )
        else:
            checks.append(RuleResult("DOCUMENT_TYPE_MISMATCH", "PASS", "Basic type check passed."))

    # 7) Year check for degree/marksheet
    if doc.document_type in {"DEGREE_CERTIFICATE", "MARKSHEET"} and doc.mime_type == "application/pdf":
        years = re.findall(r"\b(?:19|20)\d{2}\b", extracted_text or "")
        if years:
            checks.append(RuleResult("EXPIRY_YEAR_CHECK", "PASS", "Detected year in document."))
        else:
            checks.append(
                RuleResult(
                    "EXPIRY_YEAR_CHECK",
                    "WARNING",
                    "Could not detect year of issue in document.",
                )
            )

    final_status, final_message = _status_priority(checks)
    doc.validation_status = final_status
    doc.validation_message = final_message
    doc.validated_at = datetime.now(timezone.utc)

    for check in checks:
        db.add(
            DocumentValidationLog(
                document_id=doc.id,
                application_id=doc.application_id,
                check_type=check.check_type,
                result=check.result,
                message=check.message,
            )
        )

    await db.commit()
    return ValidationResult(status=final_status, message=final_message, checks=checks)


async def run_document_validation_task(document_id: UUID) -> None:
    """Background task wrapper that opens its own DB session."""
    async with AsyncSessionLocal() as db:
        await run_document_validation(document_id, db)
