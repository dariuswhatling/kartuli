"""Recognise a hand-drawn Georgian letter via Google Cloud Vision API."""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from PIL import Image, ImageOps

from .alphabet import LETTERS

logger = logging.getLogger(__name__)

VISION_URL = "https://vision.googleapis.com/v1/images:annotate"
GEORGIAN_LETTER_RE = re.compile(r"[\u10A0-\u10FF]")
KNOWN_LETTERS = frozenset(LETTERS)
MIN_EXPORT_SIDE = 512


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


def _prepare_image_for_vision(image_bytes: bytes) -> bytes:
    """Crop to ink, upscale, and boost contrast so Vision can read phone drawings."""
    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    pixels = list(img.getdata())
    if not pixels:
        raise ValueError("empty image")

    width, height = img.size
    threshold = 235
    ink_coords = [
        (x, y)
        for y in range(height)
        for x in range(width)
        if pixels[y * width + x] < threshold
    ]
    if not ink_coords:
        raise ValueError("no ink")

    xs = [c[0] for c in ink_coords]
    ys = [c[1] for c in ink_coords]
    pad = max(12, int(max(width, height) * 0.08))
    left = max(0, min(xs) - pad)
    top = max(0, min(ys) - pad)
    right = min(width, max(xs) + pad)
    bottom = min(height, max(ys) + pad)
    cropped = img.crop((left, top, right, bottom))

    side = max(cropped.size)
    scale = max(1, MIN_EXPORT_SIDE / side)
    new_w = max(1, int(cropped.width * scale))
    new_h = max(1, int(cropped.height * scale))
    cropped = cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Bold black strokes on white (Vision reads this best).
    cropped = ImageOps.autocontrast(cropped, cutoff=1)
    bw = cropped.point(lambda p: 0 if p < 200 else 255, mode="L")
    rgb = Image.new("RGB", bw.size, (255, 255, 255))
    rgb.paste(bw)

    margin = int(max(rgb.size) * 0.15)
    padded = Image.new(
        "RGB",
        (rgb.width + 2 * margin, rgb.height + 2 * margin),
        (255, 255, 255),
    )
    padded.paste(rgb, (margin, margin))

    out = io.BytesIO()
    padded.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _extract_georgian_letter(text: str) -> str | None:
    """Return the first Georgian letter from Vision OCR output."""
    chars = GEORGIAN_LETTER_RE.findall(text)
    if not chars:
        return None
    for ch in chars:
        if ch in KNOWN_LETTERS:
            return ch
    return chars[0]


def _vision_text_from_response(response: dict) -> str:
    full = response.get("fullTextAnnotation") or {}
    text = (full.get("text") or "").strip()
    if text:
        return text
    annotations = response.get("textAnnotations") or []
    if annotations:
        return (annotations[0].get("description") or "").strip()
    return ""


def _call_vision_api(image_bytes: bytes, *, use_document: bool) -> dict:
    api_key = _api_key()
    feature_type = "DOCUMENT_TEXT_DETECTION" if use_document else "TEXT_DETECTION"
    body = {
        "requests": [
            {
                "image": {"content": base64.b64encode(image_bytes).decode("ascii")},
                "features": [{"type": feature_type}],
                "imageContext": {"languageHints": ["ka", "en"]},
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
        detail = e.read().decode("utf-8", errors="replace")[:800]
        logger.warning("Vision API HTTP %s: %s", e.code, detail)
        raise VisionNotConfigured(f"Vision API error ({e.code}): {detail}") from e
    except urllib.error.URLError as e:
        raise VisionNotConfigured(f"Vision API connection failed: {e.reason}") from e


def _parse_vision_payload(payload: dict) -> tuple[str, str]:
    """Return (raw_text, error_message). error_message empty on success."""
    responses = payload.get("responses") or []
    if not responses:
        return "", "No response from Vision API."

    first = responses[0]
    if "error" in first:
        err = first["error"]
        return "", err.get("message", "Vision API returned an error.")

    raw_text = _vision_text_from_response(first)
    return raw_text, ""


def recognize_letter_image(image_bytes: bytes) -> RecognitionResult:
    if not image_bytes:
        return RecognitionResult(None, 0.0, message="No image was sent.")

    try:
        prepared = _prepare_image_for_vision(image_bytes)
    except ValueError:
        return RecognitionResult(
            None, 0.0, message="Draw a letter in the box first.",
        )
    except Exception as e:
        logger.exception("Image prepare failed")
        prepared = image_bytes  # fall back to raw upload

    try:
        _api_key()
    except VisionNotConfigured as e:
        return RecognitionResult(None, 0.0, message=str(e))

    raw_text = ""
    last_error = ""

    for use_document in (True, False):
        try:
            payload = _call_vision_api(prepared, use_document=use_document)
        except VisionNotConfigured as e:
            return RecognitionResult(None, 0.0, message=str(e))

        text, err = _parse_vision_payload(payload)
        if err:
            last_error = err
            continue
        if text:
            raw_text = text
            break

    if not raw_text:
        logger.warning(
            "Vision returned no text (document+text tried). last_error=%r",
            last_error,
        )
        return RecognitionResult(
            None,
            0.0,
            message="Couldn't read a letter — draw larger, slower, and clearer.",
        )

    logger.info("Vision OCR raw text: %r", raw_text)

    letter = _extract_georgian_letter(raw_text)
    if not letter:
        hint = raw_text.replace("\n", " ").strip()[:40]
        if hint and all(ord(c) < 128 for c in hint if c.isalnum()):
            msg = (
                f'Google saw "{hint}" — use Georgian script (e.g. ა), not English letters.'
            )
        elif hint:
            msg = f'Google saw "{hint}" — no Georgian letter found. Try again.'
        else:
            msg = "No Georgian letter detected — draw one Georgian letter."
        return RecognitionResult(None, 0.0, message=msg, raw_text=raw_text)

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
        "correct": correct if result.letter else False,
        "message": result.message,
        "expected": expected or None,
        "raw_text": result.raw_text or None,
    }
