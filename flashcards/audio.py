"""Filename + URL helpers shared by views and the generate_audio command."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
    from .models import Card, CommonWordCard


ALPHABET_DIR = "audio/alphabet"
COMMON_WORDS_DIR = "audio/common_words"


def _slugify_for_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", value)
    return cleaned[:32] or "x"


def card_filename(card: "Card") -> str:
    """Stable, content-aware filename so edited text never reuses old audio."""
    digest = hashlib.sha1((card.georgian or "").encode("utf-8")).hexdigest()[:10]
    return f"card_{card.id}_ka_{digest}.mp3"


def common_word_filename(card: "CommonWordCard") -> str:
    digest = hashlib.sha1((card.georgian or "").encode("utf-8")).hexdigest()[:10]
    return f"common_{card.id}_ka_{digest}.mp3"


def alphabet_filename(letter: str) -> str:
    digest = hashlib.sha1(letter.encode("utf-8")).hexdigest()[:8]
    return f"letter_{digest}_{_slugify_for_filename(letter)}.mp3"


def alphabet_audio_url(letter: str) -> str | None:
    """Return the public URL for the letter's recording, or None if missing."""
    filename = alphabet_filename(letter)
    path = Path(settings.MEDIA_ROOT) / ALPHABET_DIR / filename
    if not path.exists() or path.stat().st_size == 0:
        return None
    return f"{settings.MEDIA_URL}{ALPHABET_DIR}/{filename}"
