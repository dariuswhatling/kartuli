from django.contrib import admin

from .models import Attempt, Card


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ("id", "georgian", "english", "updated_at")
    search_fields = ("georgian", "english")


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "card", "direction", "correct", "created_at")
    list_filter = ("direction", "correct")
    search_fields = ("card__georgian", "card__english")
