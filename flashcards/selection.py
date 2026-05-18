"""Weighted card selection for the quiz.

The goal: cards the user keeps getting wrong (especially recently) should pop up
more often, mastered cards should still appear occasionally so the user keeps
them fresh, and brand-new cards get top priority.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable

from .models import Attempt, Card


# How many of the most-recent attempts count as "recent" for weighting.
RECENT_WINDOW = Attempt.RECENT_WINDOW

# Minimum weight floor so mastered cards still show up sometimes.
MIN_WEIGHT = 0.25

# Weight given to a brand-new card (never attempted).
NEW_CARD_WEIGHT = 6.0


@dataclass
class CardWithStats:
    card: Card
    weight: float


def _compute_weight(total: int, correct: int, recent_wrong: int) -> float:
    if total == 0:
        return NEW_CARD_WEIGHT
    accuracy = correct / total
    weight = 1.0 + 3.0 * recent_wrong + 2.0 * (1.0 - accuracy)
    return max(weight, MIN_WEIGHT)


def _gather_weights(cards: list[Card]) -> list[CardWithStats]:
    if not cards:
        return []

    card_ids = [c.id for c in cards]
    attempts = list(
        Attempt.objects.filter(card_id__in=card_ids)
        .only("card_id", "correct", "created_at")
    )
    # Attempt.Meta.ordering = ["-created_at"], so attempts are newest-first.

    by_card: dict[int, list[Attempt]] = {cid: [] for cid in card_ids}
    for a in attempts:
        by_card[a.card_id].append(a)

    results: list[CardWithStats] = []
    for card in cards:
        card_attempts = by_card[card.id]
        total = len(card_attempts)
        correct = sum(1 for a in card_attempts if a.correct)
        recent_wrong = sum(
            1 for a in card_attempts[:RECENT_WINDOW] if not a.correct
        )
        results.append(
            CardWithStats(
                card=card,
                weight=_compute_weight(total, correct, recent_wrong),
            )
        )
    return results


def pick_card(
    exclude_ids: Iterable[int] | None = None,
    single_char_only: bool = False,
) -> Card | None:
    """Return a card to quiz on, biased toward cards the user is struggling with.

    When ``single_char_only`` is True, only cards whose Georgian value is a
    single character are considered (used by the alphabet-keyboard mode).
    """
    cards = list(Card.objects.exclude(id__in=list(exclude_ids or [])))
    if single_char_only:
        cards = [c for c in cards if len(c.georgian) == 1]
    weighted = _gather_weights(cards)
    if not weighted:
        return None
    return random.choices(
        [w.card for w in weighted],
        weights=[w.weight for w in weighted],
        k=1,
    )[0]


def pick_distractors(card: Card, field: str, n: int = 2) -> list[str]:
    """Pick `n` unique distractor values from other cards' `field`."""
    correct_value = getattr(card, field)
    seen = {correct_value}
    candidates: list[str] = []
    others = list(Card.objects.exclude(id=card.id).only(field))
    random.shuffle(others)
    for other in others:
        value = getattr(other, field)
        if value in seen:
            continue
        seen.add(value)
        candidates.append(value)
        if len(candidates) >= n:
            break
    return candidates
