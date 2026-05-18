"""URL configuration for kartuli project."""

from django.contrib import admin
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz", views.healthz, name="healthz"),
    path("admin/", admin.site.urls),
]
