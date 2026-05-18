from django.db import models


class Card(models.Model):
    """A flashcard pairing a Georgian word/phrase/letter with its English equivalent."""

    georgian = models.CharField(max_length=255)
    english = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.georgian} – {self.english}"

    def stats(self) -> dict:
        attempts = list(self.attempts.all())
        total = len(attempts)
        correct = sum(1 for a in attempts if a.correct)
        recent = attempts[: Attempt.RECENT_WINDOW]
        recent_wrong = sum(1 for a in recent if not a.correct)
        return {
            "total": total,
            "correct": correct,
            "accuracy": (correct / total) if total else None,
            "recent_wrong": recent_wrong,
        }


class Attempt(models.Model):
    """A single quiz attempt against a card, in one of two directions."""

    DIRECTION_GEO_TO_EN = "geo_to_en"
    DIRECTION_EN_TO_GEO = "en_to_geo"
    DIRECTION_CHOICES = [
        (DIRECTION_GEO_TO_EN, "Georgian → English"),
        (DIRECTION_EN_TO_GEO, "English → Georgian"),
    ]

    RECENT_WINDOW = 5

    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="attempts")
    direction = models.CharField(max_length=16, choices=DIRECTION_CHOICES)
    correct = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["card", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.card_id} {self.direction} {'✓' if self.correct else '✗'}"
