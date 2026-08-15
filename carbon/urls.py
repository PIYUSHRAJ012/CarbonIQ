from django.urls import path

from . import views


app_name = "carbon"

urlpatterns = [
    path(
        "calculator/",
        views.calculator,
        name="calculator",
    ),
    path(
        "submissions/<int:pk>/result/",
        views.result,
        name="result",
    ),
]