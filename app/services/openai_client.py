import asyncio
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    from openai import AsyncOpenAI  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    AsyncOpenAI = None  # type: ignore

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if AsyncOpenAI and settings.OPENAI_API_KEY else None

SYSTEM_PROMPT = """
You are an AI assistant for a Government Education System (DTE CHB Portal).

Generate official recruitment advertisements for Clock Hour Basis (CHB) lecturers.

STRICT RULES:

* Follow formal government tone
* Ensure completeness (institution, course, vacancies, qualification, reservation, deadline, documents)
* Maintain consistency between English and Marathi versions
* Do NOT hallucinate unknown data
* Output STRICT JSON only
"""

DOCUMENT_SYSTEM_PROMPT = """
You are an AI assistant for a government recruitment system.

Your job is to analyze candidate documents using multimodal capabilities.

STRICT RULES:
* Do NOT hallucinate data
* Only use provided text and images
* Explicitly compare the photo on the Aadhar card with the candidate's uploaded photo. Verify if they match.
* Verify all textual details on the Aadhar card and Degree certificates against the candidate's profile.
* Identify mismatches clearly and list them.
* Summarize your findings in a detailed scrutiny summary.
* Output STRICT JSON
"""

SELECTION_SYSTEM_PROMPT = """
You are an AI assistant for a Government recruitment system.

Analyze candidate rankings and detect bias.

STRICT RULES:

* Do NOT modify system scores
* Only provide suggestions
* Detect bias objectively
* Output STRICT JSON only
"""


def _safe(text: str | None, limit: int = 500) -> str:
    if not text:
        return ""
    return text if len(text) <= limit else text[:limit] + "...<truncated>"


async def generate_ad(prompt: str) -> str:
    if client is None:
        raise RuntimeError("OpenAI client unavailable. Install `openai` and set OPENAI_API_KEY.")

    timeout_seconds = min(max(settings.LLM_TIMEOUT_SECONDS, 1), 30)
    logger.info("OpenAI ad prompt (truncated): %s", _safe(prompt))

    resp = await asyncio.wait_for(
        client.chat.completions.create(
            model=settings.OPENAI_MODEL or "gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        ),
        timeout=timeout_seconds,
    )
    content = (resp.choices[0].message.content or "").strip()
    logger.info("OpenAI ad response (truncated): %s", _safe(content))
    return content


def openai_ready() -> bool:
    return client is not None


async def analyze_documents(prompt: str, images: list[dict] | None = None) -> str:
    if client is None:
        raise RuntimeError("OpenAI client unavailable. Install `openai` and set OPENAI_API_KEY.")

    timeout_seconds = min(max(settings.LLM_TIMEOUT_SECONDS, 1), 60)
    logger.info("OpenAI document prompt (truncated): %s", _safe(prompt))
    
    user_content = [{"type": "text", "text": prompt}]
    if images:
        user_content.extend(images)

    resp = await asyncio.wait_for(
        client.chat.completions.create(
            model=settings.OPENAI_MODEL or "gpt-4o",  # Prefer gpt-4o for vision tasks
            temperature=0.1,
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": DOCUMENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        ),
        timeout=timeout_seconds,
    )
    content = (resp.choices[0].message.content or "").strip()
    logger.info("OpenAI document response (truncated): %s", _safe(content))
    return content


async def call_llm_selection(prompt: str) -> str | None:
    if client is None:
        logger.error("OpenAI client unavailable for selection analysis.")
        return None

    try:
        timeout_seconds = 30  # Increased timeout to prevent TimeoutError
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.OPENAI_MODEL or "gpt-4o-mini",
                temperature=0.1,
                response_format={ "type": "json_object" },
                messages=[
                    {"role": "system", "content": SELECTION_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            ),
            timeout=timeout_seconds,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logger.error(f"Error calling OpenAI for selection: {str(e)}")
        return None

async def call_llm_attendance(prompt: str) -> str | None:
    if client is None:
        logger.error("OpenAI client unavailable for attendance analysis.")
        return None

    timeout_seconds = 5
    
    for attempt in range(2): # max 1 retry
        try:
            resp = await asyncio.wait_for(
                client.chat.completions.create(
                    model=settings.OPENAI_MODEL or "gpt-4o-mini",
                    temperature=0.1,
                    response_format={ "type": "json_object" },
                    messages=[
                        {"role": "system", "content": "You are an AI analyzing faculty attendance logs. Return strict JSON."},
                        {"role": "user", "content": prompt},
                    ],
                ),
                timeout=timeout_seconds,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            logger.warning(f"Error calling OpenAI for attendance (attempt {attempt+1}): {str(e)}")
            if attempt == 1:
                return None
    return None

async def call_llm_billing(prompt: str) -> str | None:
    if client is None:
        logger.error("OpenAI client unavailable for billing validation.")
        return None

    timeout_seconds = 5
    
    for attempt in range(2): # max 1 retry
        try:
            resp = await asyncio.wait_for(
                client.chat.completions.create(
                    model=settings.OPENAI_MODEL or "gpt-4o-mini",
                    temperature=0.1,
                    response_format={ "type": "json_object" },
                    messages=[
                        {"role": "system", "content": "You are validating a faculty bill in a government system. Output strict JSON."},
                        {"role": "user", "content": prompt},
                    ],
                ),
                timeout=timeout_seconds,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            logger.warning(f"Error calling OpenAI for billing (attempt {attempt+1}): {str(e)}")
            if attempt == 1:
                return None
    return None

async def call_llm_count_faces(base64_image: str) -> int | None:
    if client is None:
        logger.error("OpenAI client unavailable for face counting.")
        return None

    try:
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model="gpt-4o",
                temperature=0.0,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Count the exact number of human faces/students visible in this image. Return STRICTLY a single integer representing the count, and absolutely nothing else."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
            ),
            timeout=15,
        )
        content = (resp.choices[0].message.content or "").strip()
        import re
        match = re.search(r'\d+', content)
        if match:
            return int(match.group())
        return None
    except Exception as e:
        logger.error(f"Error calling OpenAI for face counting: {str(e)}")
        return None
