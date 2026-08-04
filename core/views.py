from django.shortcuts import render


def home(request):
    """
    Render the application's landing page.
    """
    return render(request, "core/home.html")