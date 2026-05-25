from django.contrib import admin

from .models import Card, Chapter, CommonWordCard, CommonWordChapter


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


class CommonWordCardInline(admin.TabularInline):
    model = CommonWordCard
    extra = 0
    fields = ("georgian", "romanised", "english", "sort_order")
    ordering = ("sort_order",)


@admin.register(CommonWordChapter)
class CommonWordChapterAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "sort_order")
    ordering = ("sort_order",)
    inlines = [CommonWordCardInline]


@admin.register(CommonWordCard)
class CommonWordCardAdmin(admin.ModelAdmin):
    list_display = ("id", "chapter", "georgian", "english", "romanised")
    list_filter = ("chapter",)
    search_fields = ("georgian", "english", "romanised")
