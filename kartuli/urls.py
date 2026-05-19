"""URL configuration for kartuli project."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as static_serve

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz", views.healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("", include("flashcards.urls")),
    # Audio recordings live on a persistent volume; serve them via Django.
    # Personal-scale traffic only, so the built-in static-serve view is fine.
    re_path(
        r"^media/(?P<path>.*)$",
        static_serve,
        {"document_root": str(settings.MEDIA_ROOT)},
    ),
]
