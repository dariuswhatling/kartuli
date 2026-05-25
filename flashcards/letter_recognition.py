"""Recognise a hand-drawn Georgian letter via Tesseract (kat language pack)."""

from __future__ import annotations

import base64
import io
import logging
import re
import shutil
from dataclasses import dataclass

import pytesseract
from PIL import Image, ImageOps

from .alphabet import LETTERS

logger = logging.getLogger(__name__)

GEORGIAN_LETTER_RE = re.compile(r"[\u10A0-\u10FF]")
KNOWN_LETTERS = frozenset(LETTERS)
# ISO 639-2 code for Georgian in Tesseract (package: tesseract-ocr-kat).
TESSERACT_LANG = "kat"
GEORGIAN_WHITELIST = "".join(LETTERS)
MIN_OCR_SIDE = 512
PSM_MODES = (10, 8, 6)  # single char, single word, uniform block


class TesseractNotConfigured(RuntimeError):
    """Raised when Tesseract or the Georgian language pack is missing."""


@dataclass(frozen=True)
class RecognitionResult:
    letter: str | None
    confidence: float
    message: str = ""
    raw_text: str = ""
    source: str = ""


def _decode_image_payload(raw: str) -> bytes:
    if "," in raw:
        raw = raw.split(",", 1)[1]
    return base64.b64decode(raw)


def _ensure_tesseract() -> None:
    if not shutil.which("tesseract"):
        raise TesseractNotConfigured(
            "Tesseract is not installed. Install tesseract-ocr and tesseract-ocr-kat."
        )
    try:
        langs = pytesseract.get_languages(config="")
    except pytesseract.TesseractError as e:
        raise TesseractNotConfigured(f"Tesseract error: {e}") from e

    if TESSERACT_LANG not in langs:
        raise TesseractNotConfigured(
            f'Tesseract Georgian pack "{TESSERACT_LANG}" is not installed. '
            "Install the tesseract-ocr-kat package."
        )


def _ink_ratio(image_bytes: bytes, *, threshold: int = 240) -> float:
    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    px = img.getdata()
    if not px:
        return 0.0
    dark = sum(1 for p in px if p < threshold)
    return dark / len(px)


def _crop_to_ink(image_bytes: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    px = img.getdata()
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


def _prepare_for_ocr(image_bytes: bytes) -> Image.Image:
    """Crop to ink, upscale, and binarize for Tesseract."""
    cropped = _crop_to_ink(image_bytes)

    side = max(cropped.size)
    scale = max(1, MIN_OCR_SIDE / side)
    new_w = max(1, int(cropped.width * scale))
    new_h = max(1, int(cropped.height * scale))
    cropped = cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)
    cropped = ImageOps.autocontrast(cropped, cutoff=1)
    bw = cropped.point(lambda p: 0 if p < 200 else 255, mode="L")

    margin = int(max(bw.size) * 0.15)
    padded = Image.new("L", (bw.width + 2 * margin, bw.height + 2 * margin), 255)
    padded.paste(bw, (margin, margin))
    return padded


def _extract_georgian_letter(text: str) -> str | None:
    chars = GEORGIAN_LETTER_RE.findall(text)
    if not chars:
        return None
    for ch in chars:
        if ch in KNOWN_LETTERS:
            return ch
    return chars[0]


def _tesseract_config(psm: int) -> str:
    return (
        f"--psm {psm} --oem 1 "
        f"-c tessedit_char_whitelist={GEORGIAN_WHITELIST}"
    )


def _run_tesseract(img: Image.Image) -> tuple[str, float]:
    """OCR with Georgian-only language and character whitelist."""
    best_text = ""
    best_conf = 0.0

    for psm in PSM_MODES:
        config = _tesseract_config(psm)
        try:
            text = pytesseract.image_to_string(
                img,
                lang=TESSERACT_LANG,
                config=config,
            ).strip()
        except pytesseract.TesseractError as e:
            logger.warning("Tesseract OCR failed psm=%s: %s", psm, e)
            continue

        if not text:
            continue

        conf = _mean_confidence(img, config)
        logger.info("Tesseract psm=%s text=%r conf=%.1f", psm, text, conf)
        if conf >= best_conf or (conf == best_conf and len(text) <= len(best_text or text)):
            best_text = text
            best_conf = conf

    return best_text, best_conf


def _mean_confidence(img: Image.Image, config: str) -> float:
    try:
        data = pytesseract.image_to_data(
            img,
            lang=TESSERACT_LANG,
            config=config,
            output_type=pytesseract.Output.DICT,
        )
    except pytesseract.TesseractError:
        return 0.0

    confs = []
    for text, conf in zip(data.get("text", []), data.get("conf", [])):
        if not (text or "").strip():
            continue
        try:
            c = float(conf)
        except (TypeError, ValueError):
            continue
        if c >= 0:
            confs.append(c)

    return sum(confs) / len(confs) if confs else 0.0


def recognize_letter_image(image_bytes: bytes) -> RecognitionResult:
    if not image_bytes:
        return RecognitionResult(None, 0.0, message="No image was sent.")

    ratio = _ink_ratio(image_bytes)
    if ratio < 0.001:
        return RecognitionResult(
            None, 0.0, message="Draw a letter in the box first.",
        )

    try:
        _ensure_tesseract()
    except TesseractNotConfigured as e:
        return RecognitionResult(None, 0.0, message=str(e))

    try:
        prepared = _prepare_for_ocr(image_bytes)
    except ValueError:
        return RecognitionResult(
            None, 0.0, message="Draw a letter in the box first.",
        )
    except Exception:
        logger.exception("Image prepare failed")
        prepared = Image.open(io.BytesIO(image_bytes)).convert("L")

    logger.info(
        "Recognize request: raw=%s ink=%.4f prepared=%sx%s",
        _image_size_label(image_bytes),
        ratio,
        prepared.width,
        prepared.height,
    )

    raw_text, conf = _run_tesseract(prepared)
    if not raw_text:
        return RecognitionResult(
            None,
            0.0,
            message="Couldn't read that — draw the Georgian letter larger and clearer.",
        )

    letter = _extract_georgian_letter(raw_text)
    if not letter:
        hint = raw_text.replace("\n", " ").strip()[:40]
        return RecognitionResult(
            None,
            0.0,
            message=f'Read "{hint}" — draw one Georgian letter from the alphabet.',
            raw_text=raw_text,
        )

    confidence = max(0.1, min(1.0, conf / 100.0)) if conf else 0.75
    return RecognitionResult(
        letter,
        confidence,
        raw_text=raw_text,
        source="tesseract",
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
