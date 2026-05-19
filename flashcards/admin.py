from django.contrib import admin

from .models import Card, Chapter


class CardInline(admin.TabularInline):
    model = Card
    extra = 0
    fields = ("romanised", "english", "georgian")


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "updated_at")
    search_fields = ("name",)
    inlines = [CardInline]


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ("id", "chapter", "romanised", "english", "georgian", "updated_at")
    list_filter = ("chapter",)
    search_fields = ("romanised", "english", "georgian")
