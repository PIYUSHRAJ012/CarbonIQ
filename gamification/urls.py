from django.urls import path

from . import views


app_name = "gamification"


urlpatterns = [
    path(
        "challenges/<int:challenge_id>/join/",
        views.join_challenge_view,
        name="join_challenge",
    ),
]