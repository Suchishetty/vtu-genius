from django.shortcuts import render

# Create your views here.

def home(request):
    return render(request, 'landing_page.html')


def login_view(request):
    from django.http import HttpResponse
    return HttpResponse('Login page placeholder')


def register_view(request):
    from django.http import HttpResponse
    return HttpResponse('Register page placeholder')
