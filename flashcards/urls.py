from django.urls import path

from . import views

urlpatterns = [
    path("quiz/", views.quiz_page, name="quiz"),
    path("dictionary/", views.dictionary_page, name="dictionary"),
    path("api/quiz/next/", views.api_next, name="api_quiz_next"),
    path("api/quiz/answer/", views.api_answer, name="api_quiz_answer"),
    path("api/cards/", views.api_cards, name="api_cards"),
    path("api/cards/<int:card_id>/", views.api_card_detail, name="api_card_detail"),
]
