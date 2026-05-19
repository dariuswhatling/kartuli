"""Generate Cartesia TTS recordings for every dictionary card and alphabet letter.

The command is idempotent: it skips cards that already have audio and skips
alphabet letters whose file already exists on disk. It's designed to run on
every deploy (kicked off in the background from start.sh) so adding new
cards or letters between deploys eventually catches up after a redeploy.
"""

from __future__ import annotations

import time
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from flashcards.alphabet import ALPHABET
from flashcards.audio import (
    ALPHABET_DIR,
    alphabet_filename,
    card_filename,
)
from flashcards.cartesia import (
    CartesiaConfig,
    CartesiaError,
    CartesiaNotConfigured,
    synthesise,
)
from flashcards.models import Card


class Command(BaseCommand):
    help = (
        "Generate any missing Cartesia TTS recordings for dictionary cards "
        "and the static alphabet. Safe to run repeatedly."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-cards",
            action="store_true",
            help="Don't generate card audio.",
        )
        parser.add_argument(
            "--skip-alphabet",
            action="store_true",
            help="Don't generate alphabet audio.",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=0.0,
            help="Seconds to sleep between calls (gentle rate-limiting).",
        )

    def handle(self, *args, **opts):
        try:
            config = CartesiaConfig.from_env()
        except CartesiaNotConfigured as e:
            self.stderr.write(self.style.WARNING(f"Skipping audio generation: {e}"))
            return

        sleep_s = float(opts["sleep"])

        media_root = Path(settings.MEDIA_ROOT)
        (media_root / ALPHABET_DIR).mkdir(parents=True, exist_ok=True)

        stats = {
            "card_added": 0,
            "card_skipped": 0,
            "card_failed": 0,
            "letter_added": 0,
            "letter_skipped": 0,
            "letter_failed": 0,
        }

        if not opts["skip_cards"]:
            self._generate_cards(config, stats, sleep_s)

        if not opts["skip_alphabet"]:
            self._generate_alphabet(config, stats, media_root, sleep_s)

        self.stdout.write(
            self.style.SUCCESS(
                "Audio sync done — "
                f"cards: added {stats['card_added']}, skipped {stats['card_skipped']}, "
                f"failed {stats['card_failed']} | "
                f"letters: added {stats['letter_added']}, skipped {stats['letter_skipped']}, "
                f"failed {stats['letter_failed']}"
            )
        )

    # ------------------------------------------------------------------ cards

    def _generate_cards(self, config, stats, sleep_s):
        cards = list(Card.objects.all())
        self.stdout.write(f"Checking {len(cards)} card(s) for missing audio…")

        for card in cards:
            text = (card.georgian or "").strip()
            if not text:
                stats["card_skipped"] += 1
                continue
            if card.audio_georgian and card.audio_georgian.name:
                stats["card_skipped"] += 1
                continue

            filename = card_filename(card)
            try:
                audio_bytes = synthesise(text, config=config)
            except CartesiaError as e:
                stats["card_failed"] += 1
                self.stderr.write(self.style.WARNING(f"  card {card.id}: {e}"))
                continue

            card.audio_georgian.save(filename, ContentFile(audio_bytes), save=False)
            stats["card_added"] += 1
            self.stdout.write(f"  card {card.id} -> {filename}")
            card.save(update_fields=["audio_georgian", "updated_at"])
            if sleep_s:
                time.sleep(sleep_s)

    # --------------------------------------------------------------- alphabet

    def _generate_alphabet(self, config, stats, media_root, sleep_s):
        target_dir = media_root / ALPHABET_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        self.stdout.write(
            f"Checking {len(ALPHABET)} alphabet letter(s) under {target_dir}…"
        )

        for letter, _sound in ALPHABET:
            filename = alphabet_filename(letter)
            out_path = target_dir / filename
            if out_path.exists() and out_path.stat().st_size > 0:
                stats["letter_skipped"] += 1
                continue
            try:
                audio_bytes = synthesise(letter, config=config)
            except CartesiaError as e:
                stats["letter_failed"] += 1
                self.stderr.write(self.style.WARNING(f"  letter {letter}: {e}"))
                continue
            out_path.write_bytes(audio_bytes)
            stats["letter_added"] += 1
            self.stdout.write(f"  letter {letter} -> {filename}")
            if sleep_s:
                time.sleep(sleep_s)


