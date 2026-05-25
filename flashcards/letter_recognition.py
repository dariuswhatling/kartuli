"""Recognise a hand-drawn Georgian letter against alphabet templates.

Uses normalised cross-correlation on binarised, centred 64×64 glyphs rendered
with Noto Sans Georgian. Works best for deliberate single-letter drawing in
the on-screen box (phone finger or mouse), not cursive sentences.
"""

from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .alphabet import LETTERS

logger = logging.getLogger(__name__)

CANVAS_SIZE = 64
# Minimum best-template correlation to accept a guess.
MIN_SCORE = 0.42
# Best must beat the runner-up by at least this much.
MIN_MARGIN = 0.06

_FONT_CANDIDATES = (
    Path("/usr/share/fonts/truetype/noto/NotoSansGeorgian-Regular.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansGeorgian-Regular.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSansGeorgian[wdth,wght].ttf"),
    Path(__file__).resolve().parent.parent
    / "static"
    / "fonts"
    / "NotoSansGeorgian-Regular.ttf",
)


@dataclass(frozen=True)
class RecognitionResult:
    letter: str | None
    confidence: float
    message: str = ""


def _find_font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), 52)
            except OSError:
                continue
    logger.warning(
        "Georgian font not found; letter recognition may be inaccurate. "
        "Install fonts-noto-extra (Docker) or place NotoSansGeorgian-Regular.ttf "
        "in static/fonts/."
    )
    return ImageFont.load_default()


def _to_bitmap(img: Image.Image) -> np.ndarray | None:
    """Centre ink in a CANVAS_SIZE square; return float array 0–1 or None if empty."""
    gray = np.asarray(img.convert("L"), dtype=np.float32)
    ink = gray < 200
    if not ink.any():
        return None

    rows = np.where(ink.any(axis=1))[0]
    cols = np.where(ink.any(axis=0))[0]
    crop = gray[rows[0] : rows[-1] + 1, cols[0] : cols[-1] + 1]
    ch, cw = crop.shape
    if ch < 2 or cw < 2:
        return None

    side = max(ch, cw)
    pad = int(side * 0.15)
    padded = np.full((ch + 2 * pad, cw + 2 * pad), 255.0, dtype=np.float32)
    padded[pad : pad + ch, pad : pad + cw] = crop

    pil = Image.fromarray(padded.astype(np.uint8), mode="L")
    pil = pil.resize((CANVAS_SIZE, CANVAS_SIZE), Image.Resampling.LANCZOS)
    arr = np.asarray(pil, dtype=np.float32) / 255.0
    return 1.0 - arr  # ink = 1, background = 0


def _render_letter_glyph(letter: str, font: ImageFont.FreeTypeFont) -> np.ndarray:
    size = 128
    img = Image.new("L", (size, size), 255)
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), letter, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (size - tw) / 2 - bbox[0]
    y = (size - th) / 2 - bbox[1]
    draw.text((x, y), letter, fill=0, font=font)
    bitmap = _to_bitmap(img)
    if bitmap is None:
        raise RuntimeError(f"Failed to render template for {letter!r}")
    return bitmap


@lru_cache(maxsize=1)
def _letter_templates() -> dict[str, np.ndarray]:
    font = _find_font()
    return {letter: _render_letter_glyph(letter, font) for letter in LETTERS}


def _ncc(a: np.ndarray, b: np.ndarray) -> float:
    af = a.ravel().astype(np.float64)
    bf = b.ravel().astype(np.float64)
    af -= af.mean()
    bf -= bf.mean()
    denom = np.linalg.norm(af) * np.linalg.norm(bf)
    if denom < 1e-9:
        return 0.0
    return float(np.dot(af, bf) / denom)


def _decode_image_payload(raw: str) -> bytes:
    if "," in raw:
        raw = raw.split(",", 1)[1]
    return base64.b64decode(raw)


def recognize_letter_image(image_bytes: bytes) -> RecognitionResult:
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception:
        return RecognitionResult(None, 0.0, message="Invalid image data.")

    drawn = _to_bitmap(img)
    if drawn is None:
        return RecognitionResult(None, 0.0, message="Draw a letter in the box first.")

    try:
        templates = _letter_templates()
    except Exception as e:
        logger.exception("Letter templates unavailable")
        return RecognitionResult(None, 0.0, message=f"Recognition unavailable: {e}")

    scores = {letter: _ncc(drawn, tmpl) for letter, tmpl in templates.items()}
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_letter, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0

    if best_score < MIN_SCORE or (best_score - second_score) < MIN_MARGIN:
        return RecognitionResult(
            None,
            best_score,
            message="Couldn't read that — try drawing larger and clearer.",
        )

    return RecognitionResult(best_letter, best_score, message="")


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
    }
