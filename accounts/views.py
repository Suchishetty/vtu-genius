from django.shortcuts import render


def home(request):
    return render(request, "landing_page.html")
