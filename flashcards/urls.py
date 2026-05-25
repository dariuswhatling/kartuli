from django.urls import path

from . import views

urlpatterns = [
    path("quiz/", views.quiz_setup_page, name="quiz"),
    path("quiz/play/", views.quiz_play_page, name="quiz_play"),
    path("flashcard/", views.flashcard_setup_page, name="flashcard"),
    path("flashcard/play/", views.flashcard_play_page, name="flashcard_play"),
    path("keyboard/", views.keyboard_page, name="keyboard"),
    path("dictionary/", views.dictionary_page, name="dictionary"),
    path("1000-words/", views.common_words_page, name="common_words"),
    path("api/quiz/next/", views.api_next, name="api_quiz_next"),
    path("api/flashcard/next/", views.api_flashcard_next, name="api_flashcard_next"),
    path("api/alphabet/", views.api_alphabet, name="api_alphabet"),
    path("api/chapters/", views.api_chapters, name="api_chapters"),
    path(
        "api/chapters/<int:chapter_id>/",
        views.api_chapter_detail,
        name="api_chapter_detail",
    ),
    path("api/cards/", views.api_cards, name="api_cards"),
    path("api/cards/<int:card_id>/", views.api_card_detail, name="api_card_detail"),
    path("api/import/csv/", views.api_import_csv, name="api_import_csv"),
    path("api/common-words/", views.api_common_words, name="api_common_words"),
]
