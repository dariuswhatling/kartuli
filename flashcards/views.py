from __future__ import annotations

import csv
import io
import json
import random

from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .alphabet import ALPHABET
from .audio import alphabet_audio_url
from .models import Card, Chapter, CommonWordCard, CommonWordChapter
from .reading_similarity import pick_similar_romanised_distractors
from .tts_sync import schedule_card_audio_if_needed, schedule_cards_audio


# The six possible (prompt-field, answer-field) directions for the quiz.
DIRECTIONS: tuple[tuple[str, str], ...] = (
    ("romanised", "english"),
    ("english", "romanised"),
    ("georgian", "english"),
    ("english", "georgian"),
    ("romanised", "georgian"),
    ("georgian", "romanised"),
)

VALID_FIELDS: frozenset[str] = frozenset({"romanised", "english", "georgian"})

FIELD_LABELS = {
    "romanised": "Romanised",
    "english": "English",
    "georgian": "Georgian",
}


# --- Pages --------------------------------------------------------------------


@ensure_csrf_cookie
def quiz_setup_page(request: HttpRequest) -> HttpResponse:
    return render(request, "quiz_setup.html")


@ensure_csrf_cookie
def quiz_play_page(request: HttpRequest) -> HttpResponse:
    return render(request, "quiz.html")


@ensure_csrf_cookie
def keyboard_page(request: HttpRequest) -> HttpResponse:
    return render(request, "keyboard.html")


@ensure_csrf_cookie
def flashcard_setup_page(request: HttpRequest) -> HttpResponse:
    return render(request, "flashcard_setup.html")


@ensure_csrf_cookie
def flashcard_play_page(request: HttpRequest) -> HttpResponse:
    return render(request, "flashcard.html")


@ensure_csrf_cookie
def dictionary_page(request: HttpRequest) -> HttpResponse:
    return render(request, "dictionary.html")


@ensure_csrf_cookie
def common_words_page(request: HttpRequest) -> HttpResponse:
    return render(request, "common_words.html")


@ensure_csrf_cookie
def reading_setup_page(request: HttpRequest) -> HttpResponse:
    return render(request, "reading_setup.html")


@ensure_csrf_cookie
def reading_play_page(request: HttpRequest) -> HttpResponse:
    return render(request, "reading.html")


# --- Serialisers --------------------------------------------------------------


def _card_to_dict(card: Card) -> dict:
    return {
        "id": card.id,
        "chapter_id": card.chapter_id,
        "romanised": card.romanised,
        "english": card.english,
        "georgian": card.georgian,
        "audio_georgian_url": card.audio_georgian.url if card.audio_georgian else None,
    }


# Only Georgian-script (and romanised, which shares it) get audio playback.
FIELD_TO_AUDIO_ATTR = {
    "romanised": "audio_georgian",
    "georgian": "audio_georgian",
}


def _card_audio_for_field(card: Card, field: str) -> str | None:
    attr = FIELD_TO_AUDIO_ATTR.get(field)
    if not attr:
        return None
    f = getattr(card, attr)
    return f.url if f else None


def _common_word_audio_url(card: CommonWordCard) -> str | None:
    if card.audio_georgian and card.audio_georgian.name:
        return card.audio_georgian.url
    return None


def _common_word_card_to_dict(card: CommonWordCard) -> dict:
    return {
        "id": card.id,
        "chapter_id": card.chapter_id,
        "georgian": card.georgian,
        "english": card.english,
        "romanised": card.romanised,
        "audio_georgian_url": _common_word_audio_url(card),
    }


def _common_word_chapter_to_dict(
    chapter: CommonWordChapter, cards: list[CommonWordCard] | None = None
) -> dict:
    if cards is None:
        cards = list(chapter.cards.all())
    return {
        "id": chapter.id,
        "name": chapter.name,
        "slug": chapter.slug,
        "cards": [_common_word_card_to_dict(c) for c in cards],
    }


def _chapter_to_dict(chapter: Chapter, cards: list[Card] | None = None) -> dict:
    if cards is None:
        cards = list(chapter.cards.all())
    return {
        "id": chapter.id,
        "name": chapter.name,
        "cards": [_card_to_dict(c) for c in cards],
    }


def _parse_int_list(raw: str) -> list[int]:
    out: list[int] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if part.isdigit():
            out.append(int(part))
    return out


# --- Quiz API -----------------------------------------------------------------


@require_GET
def api_next(request: HttpRequest) -> JsonResponse:
    chapter_ids = _parse_int_list(request.GET.get("chapters", ""))
    last_id_raw = request.GET.get("last_id", "")
    last_id = int(last_id_raw) if last_id_raw.isdigit() else None

    requested_fields = {
        f.strip()
        for f in request.GET.get("fields", "").split(",")
        if f.strip() in VALID_FIELDS
    }
    if not requested_fields:
        requested_fields = set(VALID_FIELDS)
    if len(requested_fields) < 2:
        return JsonResponse(
            {
                "error": "need_two_fields",
                "message": "Pick at least two test fields.",
            },
            status=400,
        )

    allowed_directions = [
        (p, a) for (p, a) in DIRECTIONS
        if p in requested_fields and a in requested_fields
    ]
    if not allowed_directions:
        return JsonResponse(
            {
                "error": "no_directions",
                "message": "No valid prompt/answer combinations for those fields.",
            },
            status=400,
        )

    cards_qs = Card.objects.all()
    if chapter_ids:
        cards_qs = cards_qs.filter(chapter_id__in=chapter_ids)

    # Only quiz on cards where every requested field has content.
    complete = [
        c for c in cards_qs
        if all(getattr(c, f) for f in requested_fields)
    ]

    if not complete:
        labels = ", ".join(FIELD_LABELS[f] for f in sorted(requested_fields))
        return JsonResponse(
            {
                "error": "no_cards",
                "message": (
                    f"No cards in the selected chapters have all of: {labels}."
                ),
            },
            status=404,
        )

    if len(complete) < 3:
        return JsonResponse(
            {
                "error": "not_enough_cards",
                "message": "Need at least 3 matching cards to play.",
            },
            status=404,
        )

    pool = [c for c in complete if c.id != last_id] or complete
    card = random.choice(pool)

    prompt_field, answer_field = random.choice(allowed_directions)
    prompt = getattr(card, prompt_field)
    answer = getattr(card, answer_field)

    distractor_pool = [
        getattr(c, answer_field)
        for c in complete
        if c.id != card.id and getattr(c, answer_field) != answer
    ]
    random.shuffle(distractor_pool)
    distractors: list[str] = []
    seen = {answer}
    for value in distractor_pool:
        if value in seen:
            continue
        seen.add(value)
        distractors.append(value)
        if len(distractors) >= 3:
            break

    option_values = [answer] + distractors
    random.shuffle(option_values)

    # Map each displayed answer text to audio from any card that has it.
    value_to_audio: dict[str, str | None] = {}
    for c in complete:
        val = getattr(c, answer_field)
        if val and val not in value_to_audio:
            value_to_audio[val] = _card_audio_for_field(c, answer_field)

    options = [
        {"value": val, "audio_url": value_to_audio.get(val)}
        for val in option_values
    ]

    return JsonResponse(
        {
            "card_id": card.id,
            "prompt": prompt,
            "answer": answer,
            "options": options,
            "prompt_field": prompt_field,
            "answer_field": answer_field,
            "prompt_label": FIELD_LABELS[prompt_field],
            "answer_label": FIELD_LABELS[answer_field],
            "prompt_audio_url": _card_audio_for_field(card, prompt_field),
        }
    )


FLASHCARD_DIRECTIONS: tuple[tuple[str, str], ...] = (
    ("romanised", "english"),
    ("english", "romanised"),
)


@require_GET
def api_flashcard_next(request: HttpRequest) -> JsonResponse:
    """Next flashcard: romanised ↔ english only (no Georgian script)."""
    chapter_ids = _parse_int_list(request.GET.get("chapters", ""))
    last_id_raw = request.GET.get("last_id", "")
    last_id = int(last_id_raw) if last_id_raw.isdigit() else None

    cards_qs = Card.objects.all()
    if chapter_ids:
        cards_qs = cards_qs.filter(chapter_id__in=chapter_ids)

    complete = [
        c for c in cards_qs
        if c.romanised and c.english
    ]

    if not complete:
        return JsonResponse(
            {
                "error": "no_cards",
                "message": (
                    "No cards in the selected chapters have both Romanised and English."
                ),
            },
            status=404,
        )

    pool = [c for c in complete if c.id != last_id] or complete
    card = random.choice(pool)

    prompt_field, answer_field = random.choice(FLASHCARD_DIRECTIONS)
    prompt = getattr(card, prompt_field)
    answer = getattr(card, answer_field)

    return JsonResponse(
        {
            "card_id": card.id,
            "prompt": prompt,
            "answer": answer,
            "prompt_field": prompt_field,
            "answer_field": answer_field,
            "prompt_label": FIELD_LABELS[prompt_field],
            "answer_label": FIELD_LABELS[answer_field],
        }
    )


# --- Static alphabet (keyboard mode) -----------------------------------------


@require_GET
def api_alphabet(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {
            "pairs": [
                {
                    "georgian": g,
                    "sound": s,
                    "audio_url": alphabet_audio_url(g),
                }
                for g, s in ALPHABET
            ]
        }
    )


# --- 1000 words (read-only) ---------------------------------------------------


@require_GET
def api_common_words(request: HttpRequest) -> JsonResponse:
    chapters = list(
        CommonWordChapter.objects.prefetch_related("cards").all()
    )
    if not chapters:
        return JsonResponse(
            {
                "error": "not_imported",
                "message": (
                    "The 1000-word list has not been imported yet. "
                    "Run: python manage.py import_1000_words"
                ),
            },
            status=404,
        )
    return JsonResponse(
        {
            "chapters": [
                _common_word_chapter_to_dict(c, list(c.cards.all()))
                for c in chapters
            ],
            "total_words": sum(len(c.cards.all()) for c in chapters),
        }
    )


# --- Reading test (1000 words → romanised) ------------------------------------


@require_GET
def api_reading_next(request: HttpRequest) -> JsonResponse:
    """Georgian prompt with four romanised options; distractors match by prefix."""
    chapter_ids = _parse_int_list(request.GET.get("chapters", ""))
    last_id_raw = request.GET.get("last_id", "")
    last_id = int(last_id_raw) if last_id_raw.isdigit() else None

    cards_qs = CommonWordCard.objects.select_related("chapter").all()
    if chapter_ids:
        cards_qs = cards_qs.filter(chapter_id__in=chapter_ids)

    complete = [
        c
        for c in cards_qs
        if (c.georgian or "").strip() and (c.romanised or "").strip()
    ]

    if not complete:
        return JsonResponse(
            {
                "error": "no_cards",
                "message": (
                    "No words with both Georgian and romanised text in the "
                    "selected categories."
                ),
            },
            status=404,
        )

    if len(complete) < 4:
        return JsonResponse(
            {
                "error": "not_enough_cards",
                "message": "Need at least 4 words to build four answer choices.",
            },
            status=404,
        )

    pool = [c for c in complete if c.id != last_id] or complete
    card = random.choice(pool)
    answer = (card.romanised or "").strip()

    distractor_pairs = pick_similar_romanised_distractors(
        answer,
        complete,
        exclude_id=card.id,
        count=3,
    )

    value_to_audio: dict[str, str | None] = {}
    for c in complete:
        rom = (c.romanised or "").strip()
        if rom and rom not in value_to_audio:
            value_to_audio[rom] = _common_word_audio_url(c)

    option_values = [answer] + [rom for rom, _ in distractor_pairs]
    while len(option_values) < 4:
        extra = random.choice(complete)
        rom = (extra.romanised or "").strip()
        if rom and rom not in option_values:
            option_values.append(rom)
    option_values = option_values[:4]
    random.shuffle(option_values)

    options = [
        {"value": val, "audio_url": value_to_audio.get(val)}
        for val in option_values
    ]

    return JsonResponse(
        {
            "card_id": card.id,
            "georgian": card.georgian,
            "romanised": answer,
            "english": card.english,
            "answer": answer,
            "prompt_audio_url": _common_word_audio_url(card),
            "options": options,
        }
    )


# --- Chapter CRUD -------------------------------------------------------------


@require_http_methods(["GET", "POST"])
def api_chapters(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        chapters = list(Chapter.objects.prefetch_related("cards").all())
        return JsonResponse(
            {"chapters": [_chapter_to_dict(c, list(c.cards.all())) for c in chapters]}
        )

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    name = (payload.get("name") or "").strip() or "Untitled chapter"
    chapter = Chapter.objects.create(name=name)
    return JsonResponse(_chapter_to_dict(chapter, []), status=201)


@require_http_methods(["PUT", "PATCH", "DELETE"])
def api_chapter_detail(request: HttpRequest, chapter_id: int) -> JsonResponse:
    try:
        chapter = Chapter.objects.get(id=chapter_id)
    except Chapter.DoesNotExist:
        return JsonResponse({"error": "chapter_not_found"}, status=404)

    if request.method == "DELETE":
        chapter.delete()
        return JsonResponse({"deleted": chapter_id})

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    if "name" in payload:
        name = (payload["name"] or "").strip() or "Untitled chapter"
        chapter.name = name

    chapter.save()
    return JsonResponse(_chapter_to_dict(chapter, list(chapter.cards.all())))


# --- Card CRUD ----------------------------------------------------------------


@require_http_methods(["POST"])
def api_cards(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    try:
        chapter_id = int(payload["chapter_id"])
    except (KeyError, TypeError, ValueError):
        return JsonResponse({"error": "missing_chapter_id"}, status=400)

    try:
        chapter = Chapter.objects.get(id=chapter_id)
    except Chapter.DoesNotExist:
        return JsonResponse({"error": "chapter_not_found"}, status=404)

    card = Card.objects.create(
        chapter=chapter,
        romanised=(payload.get("romanised") or "").strip(),
        english=(payload.get("english") or "").strip(),
        georgian=(payload.get("georgian") or "").strip(),
    )
    schedule_card_audio_if_needed(card)
    return JsonResponse(_card_to_dict(card), status=201)


@require_http_methods(["PUT", "PATCH", "DELETE"])
def api_card_detail(request: HttpRequest, card_id: int) -> JsonResponse:
    try:
        card = Card.objects.get(id=card_id)
    except Card.DoesNotExist:
        return JsonResponse({"error": "card_not_found"}, status=404)

    if request.method == "DELETE":
        card.delete()
        return JsonResponse({"deleted": card_id})

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    for field in ("romanised", "english", "georgian"):
        if field in payload:
            setattr(card, field, (payload[field] or "").strip())

    card.save()
    schedule_card_audio_if_needed(card)
    return JsonResponse(_card_to_dict(card))


# --- CSV import ---------------------------------------------------------------


CSV_REQUIRED_COLUMNS = ("chapter", "english", "georgian", "romanised")
CSV_COLUMN_ALIASES = {
    "romanized": "romanised",  # American spelling
    "transliteration": "romanised",
}
CSV_MAX_BYTES = 2 * 1024 * 1024  # 2 MB ceiling, plenty for personal use


def _normalise_header(name: str) -> str:
    key = (name or "").strip().lower()
    return CSV_COLUMN_ALIASES.get(key, key)


@require_POST
def api_import_csv(request: HttpRequest) -> JsonResponse:
    upload = request.FILES.get("file")
    if upload is None:
        return JsonResponse(
            {"error": "missing_file", "message": "No file was uploaded."},
            status=400,
        )

    if upload.size and upload.size > CSV_MAX_BYTES:
        return JsonResponse(
            {
                "error": "file_too_large",
                "message": f"File is larger than {CSV_MAX_BYTES // 1024} KB.",
            },
            status=400,
        )

    raw = upload.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("utf-16")
        except UnicodeDecodeError:
            return JsonResponse(
                {
                    "error": "decode_failed",
                    "message": "Could not decode file. Save it as UTF-8 CSV.",
                },
                status=400,
            )

    reader = csv.reader(io.StringIO(text))
    try:
        header_row = next(reader)
    except StopIteration:
        return JsonResponse(
            {"error": "empty_file", "message": "The file is empty."},
            status=400,
        )

    headers = [_normalise_header(h) for h in header_row]
    missing = [c for c in CSV_REQUIRED_COLUMNS if c not in headers]
    if missing:
        return JsonResponse(
            {
                "error": "missing_columns",
                "message": (
                    "Missing required column(s): "
                    + ", ".join(missing)
                    + ". Expected headers: chapter, english, georgian, romanised."
                ),
            },
            status=400,
        )

    col_index = {name: headers.index(name) for name in CSV_REQUIRED_COLUMNS}

    added = 0
    skipped_duplicate = 0
    skipped_empty = 0
    added_card_ids: list[int] = []
    errors: list[dict] = []
    chapter_cache: dict[str, Chapter] = {}
    created_chapter_names: list[str] = []
    new_card_count_by_chapter: dict[int, int] = {}

    def value_at(row: list[str], key: str) -> str:
        idx = col_index[key]
        if idx >= len(row):
            return ""
        return (row[idx] or "").strip()

    with transaction.atomic():
        for line_no, row in enumerate(reader, start=2):  # header is line 1
            if not any((cell or "").strip() for cell in row):
                continue  # silently skip blank lines

            chapter_name = value_at(row, "chapter")
            if not chapter_name:
                errors.append({"row": line_no, "message": "Missing chapter name."})
                continue

            romanised = value_at(row, "romanised")
            english = value_at(row, "english")
            georgian = value_at(row, "georgian")

            if not (romanised or english or georgian):
                skipped_empty += 1
                continue

            chapter = chapter_cache.get(chapter_name)
            if chapter is None:
                chapter, was_created = Chapter.objects.get_or_create(
                    name=chapter_name
                )
                chapter_cache[chapter_name] = chapter
                if was_created:
                    created_chapter_names.append(chapter_name)

            exists = Card.objects.filter(
                chapter=chapter,
                romanised=romanised,
                english=english,
                georgian=georgian,
            ).exists()
            if exists:
                skipped_duplicate += 1
                continue

            new_card = Card.objects.create(
                chapter=chapter,
                romanised=romanised,
                english=english,
                georgian=georgian,
            )
            added += 1
            added_card_ids.append(new_card.id)
            new_card_count_by_chapter[chapter.id] = (
                new_card_count_by_chapter.get(chapter.id, 0) + 1
            )

    schedule_cards_audio(added_card_ids)

    # Cap reported errors so the response stays small
    max_errors = 20
    truncated = len(errors) > max_errors

    return JsonResponse(
        {
            "added": added,
            "skipped_duplicate": skipped_duplicate,
            "skipped_empty": skipped_empty,
            "chapters_created": created_chapter_names,
            "errors": errors[:max_errors],
            "errors_truncated": truncated,
        }
    )
