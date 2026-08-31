from django.urls import path

from . import views

app_name = "recommendations"

urlpatterns = [
    path(
        "",
        views.recommendations,
        name="list",
    ),
    path(
        "<int:recommendation_id>/complete/",
        views.complete_recommendation,
        name="complete",
    ),
    path(
        "<int:recommendation_id>/dismiss/",
        views.dismiss,
        name="dismiss",
    ),
]