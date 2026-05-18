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
