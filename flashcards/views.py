from __future__ import annotations

import json
import random

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods

from .alphabet import ALPHABET
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
        if len(distractors) >= 2:
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
        }
    )


# --- Static alphabet (keyboard mode) -----------------------------------------


@require_GET
def api_alphabet(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {"pairs": [{"georgian": g, "sound": s} for g, s in ALPHABET]}
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
