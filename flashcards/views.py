from __future__ import annotations

import json
import random

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .models import Attempt, Card
from .selection import pick_card, pick_distractors


@ensure_csrf_cookie
def quiz_page(request: HttpRequest) -> HttpResponse:
    return render(request, "quiz.html")


@ensure_csrf_cookie
def keyboard_page(request: HttpRequest) -> HttpResponse:
    return render(request, "keyboard.html")


@ensure_csrf_cookie
def dictionary_page(request: HttpRequest) -> HttpResponse:
    return render(request, "dictionary.html")


def _card_to_dict(card: Card, include_stats: bool = False) -> dict:
    data = {
        "id": card.id,
        "georgian": card.georgian,
        "english": card.english,
    }
    if include_stats:
        data["stats"] = card.stats()
    return data


# --- Quiz API -----------------------------------------------------------------


@require_GET
def api_next(request: HttpRequest) -> JsonResponse:
    last_id = request.GET.get("last_id")
    exclude_ids: list[int] = []
    if last_id and last_id.isdigit() and Card.objects.count() > 1:
        exclude_ids.append(int(last_id))

    card = pick_card(exclude_ids=exclude_ids)
    if card is None:
        return JsonResponse(
            {"error": "no_cards", "message": "Add some cards in the dictionary first."},
            status=404,
        )

    direction = random.choice([Attempt.DIRECTION_GEO_TO_EN, Attempt.DIRECTION_EN_TO_GEO])
    if direction == Attempt.DIRECTION_GEO_TO_EN:
        prompt = card.georgian
        answer = card.english
        distractor_field = "english"
    else:
        prompt = card.english
        answer = card.georgian
        distractor_field = "georgian"

    distractors = pick_distractors(card, distractor_field, n=2)
    options = [answer] + distractors
    random.shuffle(options)

    return JsonResponse(
        {
            "card_id": card.id,
            "direction": direction,
            "prompt": prompt,
            "options": options,
        }
    )


@require_GET
def api_keyboard_layout(request: HttpRequest) -> JsonResponse:
    """All distinct single-character Georgian letters in the dictionary."""
    seen: set[str] = set()
    letters: list[str] = []
    for georgian in Card.objects.order_by("id").values_list("georgian", flat=True):
        if len(georgian) == 1 and georgian not in seen:
            seen.add(georgian)
            letters.append(georgian)
    return JsonResponse({"letters": letters})


@require_GET
def api_keyboard_next(request: HttpRequest) -> JsonResponse:
    last_id = request.GET.get("last_id")
    exclude_ids: list[int] = []
    if last_id and last_id.isdigit():
        exclude_ids.append(int(last_id))

    card = pick_card(exclude_ids=exclude_ids, single_char_only=True)
    if card is None:
        return JsonResponse(
            {"error": "no_cards", "message": "Add at least one single-letter card."},
            status=404,
        )

    return JsonResponse(
        {
            "card_id": card.id,
            "direction": Attempt.DIRECTION_EN_TO_GEO,
            "prompt": card.english,
            "answer_length": len(card.georgian),
        }
    )


@require_POST
def api_answer(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    try:
        card_id = int(payload["card_id"])
    except (KeyError, TypeError, ValueError):
        return JsonResponse({"error": "missing_card_id"}, status=400)

    direction = payload.get("direction")
    chosen = payload.get("chosen", "")

    if direction not in {Attempt.DIRECTION_GEO_TO_EN, Attempt.DIRECTION_EN_TO_GEO}:
        return JsonResponse({"error": "invalid_direction"}, status=400)

    try:
        card = Card.objects.get(id=card_id)
    except Card.DoesNotExist:
        return JsonResponse({"error": "card_not_found"}, status=404)

    answer = card.english if direction == Attempt.DIRECTION_GEO_TO_EN else card.georgian
    correct = str(chosen).strip() == answer

    Attempt.objects.create(card=card, direction=direction, correct=correct)

    return JsonResponse({"correct": correct, "answer": answer})


# --- Dictionary CRUD API ------------------------------------------------------


@require_http_methods(["GET", "POST"])
def api_cards(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        cards = Card.objects.all()
        return JsonResponse(
            {"cards": [_card_to_dict(c, include_stats=True) for c in cards]}
        )

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    georgian = (payload.get("georgian") or "").strip()
    english = (payload.get("english") or "").strip()

    if not georgian or not english:
        return JsonResponse(
            {"error": "validation", "message": "Both Georgian and English are required."},
            status=400,
        )

    card = Card.objects.create(georgian=georgian, english=english)
    return JsonResponse(_card_to_dict(card, include_stats=True), status=201)


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

    if "georgian" in payload:
        georgian = (payload["georgian"] or "").strip()
        if not georgian:
            return JsonResponse(
                {"error": "validation", "message": "Georgian cannot be empty."},
                status=400,
            )
        card.georgian = georgian
    if "english" in payload:
        english = (payload["english"] or "").strip()
        if not english:
            return JsonResponse(
                {"error": "validation", "message": "English cannot be empty."},
                status=400,
            )
        card.english = english

    card.save()
    return JsonResponse(_card_to_dict(card, include_stats=True))
