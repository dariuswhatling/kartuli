"""Generate missing Cartesia TTS recordings for cards and the alphabet.

Shared by the management command, deploy hook, and dictionary/CSV APIs so
audio is created when content is added — not only on redeploy.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import close_old_connections

from .alphabet import ALPHABET
from .audio import (
    ALPHABET_DIR,
    alphabet_filename,
    card_filename,
    common_word_filename,
)
from .cartesia import (
    CartesiaConfig,
    CartesiaError,
    CartesiaNotConfigured,
    synthesise,
)
from .models import Card, CommonWordCard

logger = logging.getLogger(__name__)


def ensure_card_audio(card: Card, *, config: CartesiaConfig | None = None) -> bool:
    """Synthesise Georgian audio for `card` if missing. Returns True if generated."""
    text = (card.georgian or "").strip()
    if not text:
        return False
    if card.audio_georgian and card.audio_georgian.name:
        return False

    if config is None:
        try:
            config = CartesiaConfig.from_env()
        except CartesiaNotConfigured:
            return False

    try:
        audio_bytes = synthesise(text, config=config)
    except CartesiaError as e:
        logger.warning("TTS failed for card %s: %s", card.id, e)
        return False

    card.audio_georgian.save(card_filename(card), ContentFile(audio_bytes), save=False)
    card.save(update_fields=["audio_georgian", "updated_at"])
    logger.info("Generated audio for card %s", card.id)
    return True


def ensure_common_word_audio(
    card: CommonWordCard, *, config: CartesiaConfig | None = None
) -> bool:
    text = (card.georgian or "").strip()
    if not text:
        return False
    if card.audio_georgian and card.audio_georgian.name:
        return False

    if config is None:
        try:
            config = CartesiaConfig.from_env()
        except CartesiaNotConfigured:
            return False

    try:
        audio_bytes = synthesise(text, config=config)
    except CartesiaError as e:
        logger.warning("TTS failed for common word %s: %s", card.id, e)
        return False

    card.audio_georgian.save(
        common_word_filename(card), ContentFile(audio_bytes), save=False
    )
    card.save(update_fields=["audio_georgian", "updated_at"])
    logger.info("Generated audio for common word %s", card.id)
    return True


def sync_all_common_words(*, sleep_s: float = 0.0) -> dict[str, int]:
    stats = {"added": 0, "skipped": 0, "failed": 0}
    try:
        config = CartesiaConfig.from_env()
    except CartesiaNotConfigured:
        return stats

    for card in CommonWordCard.objects.all():
        text = (card.georgian or "").strip()
        if not text or (card.audio_georgian and card.audio_georgian.name):
            stats["skipped"] += 1
            continue
        if ensure_common_word_audio(card, config=config):
            stats["added"] += 1
        else:
            stats["failed"] += 1
        if sleep_s:
            time.sleep(sleep_s)
    return stats


def sync_all_cards(*, sleep_s: float = 0.0) -> dict[str, int]:
    """Generate missing audio for every card. Used by the management command."""
    stats = {"added": 0, "skipped": 0, "failed": 0}
    try:
        config = CartesiaConfig.from_env()
    except CartesiaNotConfigured:
        return stats

    for card in Card.objects.all():
        text = (card.georgian or "").strip()
        if not text or (card.audio_georgian and card.audio_georgian.name):
            stats["skipped"] += 1
            continue
        if ensure_card_audio(card, config=config):
            stats["added"] += 1
        else:
            stats["failed"] += 1
        if sleep_s:
            time.sleep(sleep_s)
    return stats


def sync_alphabet(*, sleep_s: float = 0.0) -> dict[str, int]:
    """Generate missing audio files for the static alphabet keyboard."""
    stats = {"added": 0, "skipped": 0, "failed": 0}
    try:
        config = CartesiaConfig.from_env()
    except CartesiaNotConfigured:
        return stats

    target_dir = Path(settings.MEDIA_ROOT) / ALPHABET_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    for letter, _sound in ALPHABET:
        filename = alphabet_filename(letter)
        out_path = target_dir / filename
        if out_path.exists() and out_path.stat().st_size > 0:
            stats["skipped"] += 1
            continue
        try:
            out_path.write_bytes(synthesise(letter, config=config))
            stats["added"] += 1
        except CartesiaError as e:
            logger.warning("TTS failed for letter %s: %s", letter, e)
            stats["failed"] += 1
        if sleep_s:
            time.sleep(sleep_s)
    return stats


def _card_audio_worker(card_id: int, sleep_after: float = 0.0) -> None:
    close_old_connections()
    try:
        card = Card.objects.get(pk=card_id)
        ensure_card_audio(card)
        if sleep_after:
            time.sleep(sleep_after)
    except Card.DoesNotExist:
        pass
    except Exception:
        logger.exception("Background TTS failed for card %s", card_id)
    finally:
        close_old_connections()


def schedule_card_audio(card_id: int) -> None:
    """Generate audio for one card in a background thread (non-blocking API)."""
    threading.Thread(
        target=_card_audio_worker,
        args=(card_id,),
        daemon=True,
        name=f"tts-card-{card_id}",
    ).start()


def schedule_cards_audio(card_ids: list[int], *, sleep_between: float = 0.1) -> None:
    """Generate audio for many cards sequentially in one background thread."""
    if not card_ids:
        return

    def _batch() -> None:
        close_old_connections()
        try:
            for card_id in card_ids:
                _card_audio_worker(card_id, sleep_after=sleep_between)
        finally:
            close_old_connections()

    threading.Thread(
        target=_batch,
        daemon=True,
        name=f"tts-batch-{len(card_ids)}",
    ).start()


def schedule_card_audio_if_needed(card: Card) -> None:
    """Queue TTS when the card has Georgian text but no recording yet."""
    if (card.georgian or "").strip() and not (card.audio_georgian and card.audio_georgian.name):
        schedule_card_audio(card.id)


def _common_word_audio_worker(card_id: int, sleep_after: float = 0.0) -> None:
    close_old_connections()
    try:
        card = CommonWordCard.objects.get(pk=card_id)
        ensure_common_word_audio(card)
        if sleep_after:
            time.sleep(sleep_after)
    except CommonWordCard.DoesNotExist:
        pass
    except Exception:
        logger.exception("Background TTS failed for common word %s", card_id)
    finally:
        close_old_connections()


def schedule_common_words_audio(card_ids: list[int], *, sleep_between: float = 0.1) -> None:
    if not card_ids:
        return

    def _batch() -> None:
        close_old_connections()
        try:
            for card_id in card_ids:
                _common_word_audio_worker(card_id, sleep_after=sleep_between)
        finally:
            close_old_connections()

    threading.Thread(
        target=_batch,
        daemon=True,
        name=f"tts-common-batch-{len(card_ids)}",
    ).start()
