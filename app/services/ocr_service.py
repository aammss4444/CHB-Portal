import logging
import os
import asyncio
from typing import Optional

from app.core.config import settings
logger = logging.getLogger(__name__)

# Attempt to import pytesseract
try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    from pdf2image import convert_from_path  # type: ignore
    PDF2IMAGE_AVAILABLE = True
except Exception:
    PDF2IMAGE_AVAILABLE = False


def _ocr_image_sync(path: str) -> str:
    return pytesseract.image_to_string(Image.open(path))  # type: ignore[name-defined]

async def extract_text(file_path: str) -> str:
    """
    Extracts text from an image or PDF.
    If Tesseract is not available, returns a simulated text based on filename 
    to facilitate pipeline testing.
    """
    if not os.path.exists(file_path):
        logger.error(f"File not found for OCR: {file_path}")
        return ""

    if TESSERACT_AVAILABLE:
        try:
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".pdf" and PDF2IMAGE_AVAILABLE:
                pages = await asyncio.to_thread(convert_from_path, file_path, first_page=1, last_page=3)
                chunks = []
                for page in pages:
                    chunks.append(await asyncio.to_thread(pytesseract.image_to_string, page))
                text = "\n".join(chunks)
            else:
                text = await asyncio.to_thread(_ocr_image_sync, file_path)
            return text.strip()
        except Exception as e:
            logger.warning("Tesseract OCR failed: %s", str(e))
    
    if not settings.ALLOW_OCR_SIMULATION:
        logger.error("OCR extraction unavailable and simulation is disabled for file: %s", file_path)
        return ""

    # Simulation logic for smoke testing and development only.
    file_name = os.path.basename(file_path).lower()
    if "degree" in file_name or "certificate" in file_name:
        return "CERTIFICATE OF DEGREE: MASTER OF TECHNOLOGY (M.TECH) IN COMPUTER SCIENCE. UNIVERSITY OF MUMBAI. YEAR 2022. GRADE: A+."
    elif "marksheet" in file_name:
        return "TRANSCRIPT / MARKSHEET. SEMESTER VIII. PERCENTAGE: 85%. UNIVERSITY OF MUMBAI. 2022."
    elif "id" in file_name or "aadhaar" in file_name:
        return "GOVERNMENT ID PROOF. NAME: TEST CANDIDATE. UID: 1234-5678-9012."
    
    return "Sample extracted text from document. Content appears to be a standard educational certificate."
