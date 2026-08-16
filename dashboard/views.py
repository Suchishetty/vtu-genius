from django.http import HttpResponse
from django.shortcuts import render


def dashboard_view(request):
    return HttpResponse("Dashboard")
