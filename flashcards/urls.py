from django.urls import path

from . import views

urlpatterns = [
    path("quiz/", views.quiz_page, name="quiz"),
    path("keyboard/", views.keyboard_page, name="keyboard"),
    path("dictionary/", views.dictionary_page, name="dictionary"),
    path("api/quiz/next/", views.api_next, name="api_quiz_next"),
    path("api/alphabet/", views.api_alphabet, name="api_alphabet"),
    path("api/cards/", views.api_cards, name="api_cards"),
    path("api/cards/<int:card_id>/", views.api_card_detail, name="api_card_detail"),
]
