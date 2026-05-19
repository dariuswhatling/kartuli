from django.db import models


class Chapter(models.Model):
    name = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.name


class Card(models.Model):
    """A flashcard with three sides: romanised, English, Georgian (script)."""

    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, related_name="cards"
    )
    romanised = models.CharField(max_length=255, blank=True)
    english = models.CharField(max_length=255, blank=True)
    georgian = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.georgian or self.romanised or '?'} – {self.english or '?'}"

    @property
    def is_complete(self) -> bool:
        return bool(self.romanised and self.english and self.georgian)
