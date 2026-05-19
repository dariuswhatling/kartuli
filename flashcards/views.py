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
from .models import Card, Chapter


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
def dictionary_page(request: HttpRequest) -> HttpResponse:
    return render(request, "dictionary.html")


# --- Serialisers --------------------------------------------------------------


def _card_to_dict(card: Card) -> dict:
    return {
        "id": card.id,
        "chapter_id": card.chapter_id,
        "romanised": card.romanised,
        "english": card.english,
        "georgian": card.georgian,
        "audio_georgian_url": card.audio_georgian.url if card.audio_georgian else None,
        "audio_english_url": card.audio_english.url if card.audio_english else None,
    }


# The romanised side reuses the Georgian recording (same word, same audio).
FIELD_TO_AUDIO_ATTR = {
    "romanised": "audio_georgian",
    "georgian": "audio_georgian",
    "english": "audio_english",
}


def _card_audio_for_field(card: Card, field: str) -> str | None:
    attr = FIELD_TO_AUDIO_ATTR.get(field)
    if not attr:
        return None
    f = getattr(card, attr)
    return f.url if f else None


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

    options = [answer] + distractors
    random.shuffle(options)

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
            "answer_audio_url": _card_audio_for_field(card, answer_field),
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

            Card.objects.create(
                chapter=chapter,
                romanised=romanised,
                english=english,
                georgian=georgian,
            )
            added += 1
            new_card_count_by_chapter[chapter.id] = (
                new_card_count_by_chapter.get(chapter.id, 0) + 1
            )

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
