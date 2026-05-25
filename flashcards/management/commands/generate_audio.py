"""Generate Cartesia TTS recordings for every dictionary card and alphabet letter.

The command is idempotent: it skips cards that already have audio and skips
alphabet letters whose file already exists on disk. It's designed to run on
every deploy (kicked off in the background from start.sh) and can also be
invoked manually. Day-to-day dictionary edits trigger TTS via tts_sync.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from flashcards.audio import ALPHABET_DIR
from flashcards.cartesia import CartesiaNotConfigured
from flashcards.tts_sync import sync_all_cards, sync_all_common_words, sync_alphabet


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
            "--skip-common-words",
            action="store_true",
            help="Don't generate 1000-word list audio.",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=0.0,
            help="Seconds to sleep between calls (gentle rate-limiting).",
        )

    def handle(self, *args, **opts):
        try:
            from flashcards.cartesia import CartesiaConfig

            CartesiaConfig.from_env()
        except CartesiaNotConfigured as e:
            self.stderr.write(self.style.WARNING(f"Skipping audio generation: {e}"))
            return

        sleep_s = float(opts["sleep"])
        Path(settings.MEDIA_ROOT, ALPHABET_DIR).mkdir(parents=True, exist_ok=True)

        card_stats = {"added": 0, "skipped": 0, "failed": 0}
        letter_stats = {"added": 0, "skipped": 0, "failed": 0}
        common_stats = {"added": 0, "skipped": 0, "failed": 0}

        if not opts["skip_cards"]:
            card_stats = sync_all_cards(sleep_s=sleep_s)

        if not opts["skip_alphabet"]:
            letter_stats = sync_alphabet(sleep_s=sleep_s)

        if not opts["skip_common_words"]:
            common_stats = sync_all_common_words(sleep_s=sleep_s)

        self.stdout.write(
            self.style.SUCCESS(
                "Audio sync done — "
                f"cards: added {card_stats['added']}, skipped {card_stats['skipped']}, "
                f"failed {card_stats['failed']} | "
                f"letters: added {letter_stats['added']}, skipped {letter_stats['skipped']}, "
                f"failed {letter_stats['failed']} | "
                f"1000 words: added {common_stats['added']}, "
                f"skipped {common_stats['skipped']}, failed {common_stats['failed']}"
            )
        )
