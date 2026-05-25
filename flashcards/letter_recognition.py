"""Recognise a hand-drawn Georgian letter via Google Cloud Vision API."""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from .alphabet import LETTERS

logger = logging.getLogger(__name__)

VISION_URL = "https://vision.googleapis.com/v1/images:annotate"
GEORGIAN_LETTER_RE = re.compile(r"[\u10A0-\u10FF]")
KNOWN_LETTERS = frozenset(LETTERS)


class VisionNotConfigured(RuntimeError):
    """Raised when GOOGLE_CLOUD_VISION_API_KEY is missing."""


@dataclass(frozen=True)
class RecognitionResult:
    letter: str | None
    confidence: float
    message: str = ""
    raw_text: str = ""


def _api_key() -> str:
    key = os.environ.get("GOOGLE_CLOUD_VISION_API_KEY", "").strip()
    if not key:
        raise VisionNotConfigured(
            "GOOGLE_CLOUD_VISION_API_KEY is not set. "
            "Create a Google Cloud Vision API key and add it to your environment."
        )
    return key


def _decode_image_payload(raw: str) -> bytes:
    if "," in raw:
        raw = raw.split(",", 1)[1]
    return base64.b64decode(raw)


def _extract_georgian_letter(text: str) -> str | None:
    """Return the first Georgian letter found in Vision OCR output."""
    for ch in text.replace("\n", "").replace(" ", ""):
        if GEORGIAN_LETTER_RE.match(ch) and ch in KNOWN_LETTERS:
            return ch
    match = GEORGIAN_LETTER_RE.search(text)
    if not match:
        return None
    letter = match.group(0)
    return letter if letter in KNOWN_LETTERS else letter[0]


def _call_vision_api(image_bytes: bytes) -> dict:
    api_key = _api_key()
    body = {
        "requests": [
            {
                "image": {"content": base64.b64encode(image_bytes).decode("ascii")},
                "features": [{"type": "TEXT_DETECTION", "maxResults": 1}],
                "imageContext": {"languageHints": ["ka"]},
            }
        ]
    }
    url = f"{VISION_URL}?key={api_key}"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        logger.warning("Vision API HTTP %s: %s", e.code, detail)
        raise VisionNotConfigured(f"Vision API error ({e.code}): {detail}") from e
    except urllib.error.URLError as e:
        raise VisionNotConfigured(f"Vision API connection failed: {e.reason}") from e


def recognize_letter_image(image_bytes: bytes) -> RecognitionResult:
    if not image_bytes:
        return RecognitionResult(None, 0.0, message="No image was sent.")

    try:
        payload = _call_vision_api(image_bytes)
    except VisionNotConfigured as e:
        return RecognitionResult(None, 0.0, message=str(e))

    responses = payload.get("responses") or []
    if not responses:
        return RecognitionResult(
            None, 0.0, message="No response from Vision API.",
        )

    first = responses[0]
    if "error" in first:
        err = first["error"]
        return RecognitionResult(
            None,
            0.0,
            message=err.get("message", "Vision API returned an error."),
        )

    annotations = first.get("textAnnotations") or []
    if not annotations:
        return RecognitionResult(
            None,
            0.0,
            message="Couldn't read a letter — try drawing larger and clearer.",
        )

    raw_text = (annotations[0].get("description") or "").strip()
    letter = _extract_georgian_letter(raw_text)
    if not letter:
        return RecognitionResult(
            None,
            0.0,
            message="No Georgian letter detected — draw one letter in the box.",
            raw_text=raw_text,
        )

    return RecognitionResult(letter, 0.9, raw_text=raw_text)


def recognize_letter_payload(data_url_or_b64: str, *, expected: str = "") -> dict:
    """Return a JSON-serialisable dict for the API."""
    try:
        image_bytes = _decode_image_payload(data_url_or_b64)
    except Exception:
        return {
            "recognized": None,
            "confidence": 0.0,
            "correct": False,
            "message": "Invalid image upload.",
        }

    result = recognize_letter_image(image_bytes)
    correct = None
    if expected and result.letter:
        correct = result.letter == expected

    return {
        "recognized": result.letter,
        "confidence": round(result.confidence, 3),
        "correct": correct,
        "message": result.message,
        "expected": expected or None,
        "raw_text": result.raw_text or None,
    }
