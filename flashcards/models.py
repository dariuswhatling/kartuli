from django.db import models


class Chapter(models.Model):
    name = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.name


def _audio_upload_path(instance: "Card", filename: str) -> str:
    # filename is decided in the management command; keep upload_to predictable.
    return f"audio/cards/{filename}"


class Card(models.Model):
    """A flashcard with three sides: romanised, English, Georgian (script)."""

    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, related_name="cards"
    )
    romanised = models.CharField(max_length=255, blank=True)
    english = models.CharField(max_length=255, blank=True)
    georgian = models.CharField(max_length=255, blank=True)

    # Georgian-script audio (synthesised via Cartesia). Romanised quiz prompts
    # reuse this recording — same phrase, same pronunciation.
    audio_georgian = models.FileField(
        upload_to=_audio_upload_path, blank=True, null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.georgian or self.romanised or '?'} – {self.english or '?'}"

    @property
    def is_complete(self) -> bool:
        return bool(self.romanised and self.english and self.georgian)

    def save(self, *args, **kwargs):
        """Drop stale audio when the Georgian text changes."""
        if self.pk:
            try:
                old = Card.objects.only("georgian").get(pk=self.pk)
            except Card.DoesNotExist:
                old = None
            if old is not None:
                if old.georgian != self.georgian and self.audio_georgian:
                    self.audio_georgian.delete(save=False)
        super().save(*args, **kwargs)
