from django.http import HttpResponse, JsonResponse
from django.shortcuts import render


def home(request):
    return render(request, "home.html")


def healthz(request):
    return JsonResponse({"status": "ok"})
