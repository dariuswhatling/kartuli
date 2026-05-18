from __future__ import annotations

import json
import random

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods

from .alphabet import ALPHABET
from .models import Card


DIRECTION_GEO_TO_EN = "geo_to_en"
DIRECTION_EN_TO_GEO = "en_to_geo"


# --- Pages --------------------------------------------------------------------


@ensure_csrf_cookie
def quiz_page(request: HttpRequest) -> HttpResponse:
    return render(request, "quiz.html")


@ensure_csrf_cookie
def keyboard_page(request: HttpRequest) -> HttpResponse:
    return render(request, "keyboard.html")


@ensure_csrf_cookie
def dictionary_page(request: HttpRequest) -> HttpResponse:
    return render(request, "dictionary.html")


# --- Helpers ------------------------------------------------------------------


def _card_to_dict(card: Card) -> dict:
    return {
        "id": card.id,
        "georgian": card.georgian,
        "english": card.english,
    }


# --- Flashcard quiz API -------------------------------------------------------


@require_GET
def api_next(request: HttpRequest) -> JsonResponse:
    last_id = request.GET.get("last_id")
    exclude_ids: list[int] = []
    if last_id and last_id.isdigit() and Card.objects.count() > 1:
        exclude_ids.append(int(last_id))

    cards = list(Card.objects.exclude(id__in=exclude_ids))
    if not cards:
        return JsonResponse(
            {"error": "no_cards", "message": "Add some cards in the dictionary first."},
            status=404,
        )

    card = random.choice(cards)
    direction = random.choice([DIRECTION_GEO_TO_EN, DIRECTION_EN_TO_GEO])
    if direction == DIRECTION_GEO_TO_EN:
        prompt = card.georgian
        answer = card.english
        distractor_field = "english"
    else:
        prompt = card.english
        answer = card.georgian
        distractor_field = "georgian"

    others = list(Card.objects.exclude(id=card.id).only(distractor_field))
    random.shuffle(others)
    seen = {answer}
    distractors: list[str] = []
    for o in others:
        value = getattr(o, distractor_field)
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
            "direction": direction,
            "prompt": prompt,
            "options": options,
            "answer": answer,
        }
    )


# --- Keyboard mode API (uses the static alphabet, not the Card dictionary) ----


@require_GET
def api_alphabet(request: HttpRequest) -> JsonResponse:
    """Return the full static alphabet so the client can drive the keyboard."""
    return JsonResponse(
        {
            "pairs": [{"georgian": g, "sound": s} for g, s in ALPHABET],
        }
    )


# --- Dictionary CRUD API ------------------------------------------------------


@require_http_methods(["GET", "POST"])
def api_cards(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        cards = Card.objects.all()
        return JsonResponse({"cards": [_card_to_dict(c) for c in cards]})

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
    return JsonResponse(_card_to_dict(card))
