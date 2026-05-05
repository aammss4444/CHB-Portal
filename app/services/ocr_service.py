import logging
import os
import asyncio
import httpx
from typing import Optional

from app.core.config import settings
logger = logging.getLogger(__name__)

async def extract_text(file_path: str) -> str:
    """
    Extracts text from an image or PDF using OCR.space API.
    If the API call fails or is unavailable, and simulation is enabled,
    returns simulated text.
    """
    if not os.path.exists(file_path):
        logger.error(f"File not found for OCR: {file_path}")
        return ""

    # Attempt OCR.space API
    if settings.OCR_SPACE_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                with open(file_path, 'rb') as f:
                    files = {'file': f}
                    data = {
                        'apikey': settings.OCR_SPACE_API_KEY,
                        'language': 'eng',
                        'isOverlayRequired': False,
                        'filetype': os.path.splitext(file_path)[1].lower().replace('.', '')
                    }
                    
                    logger.info(f"Calling OCR.space API for file: {file_path}")
                    response = await client.post(
                        'https://api.ocr.space/parse/image',
                        files=files,
                        data=data
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        if result.get('IsErroredOnProcessing'):
                            logger.error(f"OCR.space Error: {result.get('ErrorMessage')}")
                        else:
                            parsed_results = result.get('ParsedResults', [])
                            if parsed_results:
                                text = parsed_results[0].get('ParsedText', '')
                                return text.strip()
                    else:
                        logger.error(f"OCR.space API HTTP Error: {response.status_code}")
        except Exception as e:
            logger.warning(f"OCR.space API call failed: {str(e)}")

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
