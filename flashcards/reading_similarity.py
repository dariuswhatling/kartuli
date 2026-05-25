"""Pick phonetically similar romanisation distractors for the reading test."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import CommonWordCard


def longest_prefix_match(left: str, right: str) -> int:
    """Count matching characters from the start (case-insensitive)."""
    a = (left or "").strip().lower()
    b = (right or "").strip().lower()
    count = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            break
        count += 1
    return count


def pick_similar_romanised_distractors(
    answer_romanised: str,
    pool: list[CommonWordCard],
    *,
    exclude_id: int,
    count: int = 3,
) -> list[tuple[str, CommonWordCard]]:
    """Return up to `count` (romanised, card) pairs most similar by prefix overlap."""
    answer_key = (answer_romanised or "").strip().lower()
    if not answer_key:
        return []

    scored: list[tuple[int, str, CommonWordCard]] = []
    for card in pool:
        if card.id == exclude_id:
            continue
        romanised = (card.romanised or "").strip()
        if not romanised:
            continue
        if romanised.lower() == answer_key:
            continue
        score = longest_prefix_match(answer_romanised, romanised)
        scored.append((score, romanised, card))

    scored.sort(key=lambda item: (-item[0], item[1].lower()))

    chosen: list[tuple[str, CommonWordCard]] = []
    seen: set[str] = set()
    for _score, romanised, card in scored:
        key = romanised.lower()
        if key in seen:
            continue
        seen.add(key)
        chosen.append((romanised, card))
        if len(chosen) >= count:
            return chosen

    remaining = [
        card
        for card in pool
        if card.id != exclude_id
        and (card.romanised or "").strip()
        and (card.romanised or "").strip().lower() not in seen
        and (card.romanised or "").strip().lower() != answer_key
    ]
    random.shuffle(remaining)
    for card in remaining:
        romanised = (card.romanised or "").strip()
        key = romanised.lower()
        if key in seen:
            continue
        seen.add(key)
        chosen.append((romanised, card))
        if len(chosen) >= count:
            break

    return chosen
