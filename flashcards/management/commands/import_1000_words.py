"""One-time import of WordMastery's 1000 most common Georgian words."""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from flashcards.models import CommonWordCard, CommonWordChapter
from flashcards.tts_sync import schedule_common_words_audio
from flashcards.wordmastery import CATEGORIES, load_vocabulary


class Command(BaseCommand):
    help = (
        "Import the 1000-word Georgian vocabulary into CommonWordChapter/Card. "
        "Skips if data already exists unless --force is passed."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete existing 1000-word data and re-import.",
        )
        parser.add_argument(
            "--download",
            action="store_true",
            help="Re-fetch main.js from WordMastery instead of bundled JSON.",
        )
        parser.add_argument(
            "--no-audio",
            action="store_true",
            help="Do not queue Cartesia TTS generation after import.",
        )

    def handle(self, *args, **options):
        if CommonWordChapter.objects.exists() and not options["force"]:
            self.stdout.write(
                self.style.WARNING(
                    "1000-word vocabulary already imported. "
                    "Use --force to replace it."
                )
            )
            return

        data = load_vocabulary(prefer_bundled=not options["download"])

        with transaction.atomic():
            if options["force"]:
                CommonWordChapter.objects.all().delete()

            if CommonWordChapter.objects.exists():
                self.stdout.write(
                    self.style.WARNING("Data already present; nothing to do.")
                )
                return

            for order, (slug, default_name) in enumerate(CATEGORIES):
                chapter_data = data.get(slug)
                if not chapter_data:
                    self.stderr.write(
                        self.style.ERROR(f"Missing category {slug!r} in source data")
                    )
                    continue

                chapter = CommonWordChapter.objects.create(
                    name=chapter_data.get("name") or default_name,
                    slug=slug,
                    sort_order=order,
                )
                words = chapter_data.get("words") or []
                cards = [
                    CommonWordCard(
                        chapter=chapter,
                        georgian=w["georgian"],
                        english=w["english"],
                        romanised=w.get("romanised") or "",
                        sort_order=idx,
                    )
                    for idx, w in enumerate(words)
                ]
                CommonWordCard.objects.bulk_create(cards)
                self.stdout.write(f"  {chapter.name}: {len(cards)} words")

        total = CommonWordCard.objects.count()
        created_card_ids = list(
            CommonWordCard.objects.values_list("id", flat=True)
        )
        self.stdout.write(self.style.SUCCESS(f"Imported {total} words in 8 chapters."))

        if not options["no_audio"] and created_card_ids:
            schedule_common_words_audio(created_card_ids)
            self.stdout.write("Queued Georgian audio generation in background.")
