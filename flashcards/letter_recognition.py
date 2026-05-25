"""Recognise a hand-drawn Georgian letter (Vision OCR + shape fallback)."""

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
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .alphabet import LETTERS

logger = logging.getLogger(__name__)

VISION_URL = "https://vision.googleapis.com/v1/images:annotate"
GEORGIAN_LETTER_RE = re.compile(r"[\u10A0-\u10FF]")
KNOWN_LETTERS = frozenset(LETTERS)
# Georgian is experimental in Vision — auto-detect misses it without this hint.
# https://cloud.google.com/vision/docs/languages
GEORGIAN_LANGUAGE_HINTS = ["ka"]
MIN_EXPORT_SIDE = 512
TEMPLATE_SIZE = 96
CONTEXT_CELL = 200

FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansGeorgian-Regular.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansGeorgian-Regular.otf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
)


class VisionNotConfigured(RuntimeError):
    """Raised when GOOGLE_CLOUD_VISION_API_KEY is missing."""


@dataclass(frozen=True)
class RecognitionResult:
    letter: str | None
    confidence: float
    message: str = ""
    raw_text: str = ""
    source: str = ""


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


def _ink_ratio(image_bytes: bytes, *, threshold: int = 240) -> float:
    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    px = img.get_flattened_data()
    if not px:
        return 0.0
    dark = sum(1 for p in px if p < threshold)
    return dark / len(px)


def _crop_to_ink(image_bytes: bytes) -> Image.Image:
    """Return a cropped grayscale image containing only the drawn ink."""
    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    px = img.get_flattened_data()
    if not px:
        raise ValueError("empty image")

    width, height = img.size
    ink_threshold = 235
    ink_coords = [
        (x, y)
        for y in range(height)
        for x in range(width)
        if px[y * width + x] < ink_threshold
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
    return img.crop((left, top, right, bottom))


def _prepare_image_for_vision(image_bytes: bytes) -> bytes:
    """Crop to ink, upscale, and boost contrast so Vision can read phone drawings."""
    cropped = _crop_to_ink(image_bytes)

    side = max(cropped.size)
    scale = max(1, MIN_EXPORT_SIDE / side)
    new_w = max(1, int(cropped.width * scale))
    new_h = max(1, int(cropped.height * scale))
    cropped = cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)

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


def _upscale_raw(image_bytes: bytes) -> bytes:
    """Upscale the full canvas when Vision fails on the cropped version."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    side = max(img.size)
    if side >= MIN_EXPORT_SIDE:
        return image_bytes
    scale = MIN_EXPORT_SIDE / side
    new_size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
    img = img.resize(new_size, Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _extract_georgian_letter(text: str) -> str | None:
    chars = GEORGIAN_LETTER_RE.findall(text)
    if not chars:
        return None
    for ch in chars:
        if ch in KNOWN_LETTERS:
            return ch
    return chars[0]


def _text_from_full_annotation(annotation: dict) -> str:
    text = (annotation.get("text") or "").strip()
    if text:
        return text

    parts: list[str] = []
    for page in annotation.get("pages") or []:
        for block in page.get("blocks") or []:
            for paragraph in block.get("paragraphs") or []:
                for word in paragraph.get("words") or []:
                    for symbol in word.get("symbols") or []:
                        sym = (symbol.get("text") or "").strip()
                        if sym:
                            parts.append(sym)
    return "".join(parts).strip()


def _vision_text_from_response(response: dict) -> str:
    full = response.get("fullTextAnnotation") or {}
    text = _text_from_full_annotation(full)
    if text:
        return text
    annotations = response.get("textAnnotations") or []
    if annotations:
        return (annotations[0].get("description") or "").strip()
    return ""


def _call_vision_api(
    image_bytes: bytes,
    *,
    use_document: bool,
    language_hints: list[str] | None,
) -> dict:
    api_key = _api_key()
    feature_type = "DOCUMENT_TEXT_DETECTION" if use_document else "TEXT_DETECTION"
    request: dict = {
        "image": {"content": base64.b64encode(image_bytes).decode("ascii")},
        "features": [{"type": feature_type}],
    }
    # language_hints required for Georgian (experimental; won't auto-detect as ka).
    request["imageContext"] = {
        "languageHints": language_hints or GEORGIAN_LANGUAGE_HINTS,
    }

    body = {"requests": [request]}
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
    responses = payload.get("responses") or []
    if not responses:
        return "", "No response from Vision API."

    first = responses[0]
    if "error" in first:
        err = first["error"]
        return "", err.get("message", "Vision API returned an error.")

    return _vision_text_from_response(first), ""


def _run_vision_passes(image_variants: list[bytes]) -> str:
    """Run Vision with Georgian language hints (ka is experimental, not auto-detected)."""
    attempts: list[tuple[bool, list[str]]] = [
        (False, GEORGIAN_LANGUAGE_HINTS),
        (True, GEORGIAN_LANGUAGE_HINTS),
    ]

    for image_bytes in image_variants:
        for use_document, hints in attempts:
            try:
                payload = _call_vision_api(
                    image_bytes,
                    use_document=use_document,
                    language_hints=hints,
                )
            except VisionNotConfigured:
                raise

            text, err = _parse_vision_payload(payload)
            if err:
                logger.debug(
                    "Vision pass failed doc=%s hints=%s: %s",
                    use_document,
                    hints,
                    err,
                )
                continue
            if text:
                logger.info(
                    "Vision OCR raw text: %r (doc=%s hints=%s)",
                    text,
                    use_document,
                    hints,
                )
                return text

    return ""


@lru_cache(maxsize=1)
def _georgian_font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    size = int(TEMPLATE_SIZE * 0.72)
    for path in FONT_PATHS:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    logger.warning("No Georgian font found; template matching may be weak.")
    return ImageFont.load_default()


@lru_cache(maxsize=1)
def _letter_templates() -> dict[str, Image.Image]:
    font = _georgian_font()
    templates: dict[str, Image.Image] = {}
    for letter in LETTERS:
        img = Image.new("L", (TEMPLATE_SIZE, TEMPLATE_SIZE), 255)
        draw = ImageDraw.Draw(img)
        bbox = draw.textbbox((0, 0), letter, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = (TEMPLATE_SIZE - tw) / 2 - bbox[0]
        y = (TEMPLATE_SIZE - th) / 2 - bbox[1]
        draw.text((x, y), letter, font=font, fill=0)
        templates[letter] = img
    return templates


def _binarize(img: Image.Image, size: int = 64) -> list[int]:
    small = img.resize((size, size), Image.Resampling.LANCZOS).convert("L")
    return [1 if p < 128 else 0 for p in small.get_flattened_data()]


def _template_match(image_bytes: bytes) -> tuple[str | None, float]:
    """Shape-match the drawing against alphabet glyphs (Vision misses lone letters)."""
    try:
        cropped = _crop_to_ink(image_bytes)
    except ValueError:
        return None, 0.0

    side = max(cropped.size)
    scale = TEMPLATE_SIZE / side
    crop = cropped.resize(
        (max(1, int(cropped.width * scale)), max(1, int(cropped.height * scale))),
        Image.Resampling.LANCZOS,
    )
    crop = ImageOps.autocontrast(crop, cutoff=1)
    crop = crop.point(lambda p: 0 if p < 200 else 255, mode="L")

    user_bits = _binarize(crop)
    scores: list[tuple[str, float]] = []
    for letter, template in _letter_templates().items():
        tpl_bits = _binarize(template)
        matches = sum(1 for a, b in zip(user_bits, tpl_bits) if a == b)
        scores.append((letter, matches / len(user_bits)))

    scores.sort(key=lambda item: item[1], reverse=True)
    if len(scores) < 2:
        return None, 0.0

    best_letter, best_score = scores[0]
    second_score = scores[1][1]
    logger.info(
        "Template match top: %s=%.3f second=%.3f (margin %.3f)",
        best_letter,
        best_score,
        scores[1][0],
        best_score - second_score,
    )

    if best_score >= MATCH_MIN_SCORE and (best_score - second_score) >= MATCH_MIN_MARGIN:
        return best_letter, best_score
    return None, best_score


def recognize_letter_image(image_bytes: bytes) -> RecognitionResult:
    if not image_bytes:
        return RecognitionResult(None, 0.0, message="No image was sent.")

    ratio = _ink_ratio(image_bytes)
    if ratio < 0.001:
        return RecognitionResult(
            None, 0.0, message="Draw a letter in the box first.",
        )

    try:
        prepared = _prepare_image_for_vision(image_bytes)
    except ValueError:
        return RecognitionResult(
            None, 0.0, message="Draw a letter in the box first.",
        )
    except Exception:
        logger.exception("Image prepare failed")
        prepared = image_bytes

    try:
        _api_key()
    except VisionNotConfigured as e:
        return RecognitionResult(None, 0.0, message=str(e))

    logger.info(
        "Recognize request: raw=%s ink=%.4f prepared=%s",
        _image_size_label(image_bytes),
        ratio,
        _image_size_label(prepared),
    )

    raw_text = ""
    try:
        raw_text = _run_vision_passes([prepared, _upscale_raw(image_bytes)])
    except VisionNotConfigured as e:
        return RecognitionResult(None, 0.0, message=str(e))

    if raw_text:
        letter = _extract_georgian_letter(raw_text)
        if letter:
            return RecognitionResult(letter, 0.9, raw_text=raw_text, source="vision")

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

    logger.warning(
        "Vision returned no text for isolated letter; trying template match (ink=%.4f)",
        ratio,
    )

    letter, score = _template_match(image_bytes)
    if letter:
        return RecognitionResult(
            letter,
            round(score, 3),
            source="template",
        )

    return RecognitionResult(
        None,
        0.0,
        message=(
            "Couldn't read that — draw the letter larger, like the printed shape."
        ),
    )


def _image_size_label(image_bytes: bytes) -> str:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        return f"{img.width}x{img.height}"
    except Exception:
        return "unknown"


def recognize_letter_payload(data_url_or_b64: str, *, expected: str = "") -> dict:
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
        "source": result.source or None,
    }
