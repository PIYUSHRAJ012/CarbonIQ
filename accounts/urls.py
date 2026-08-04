from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import (
    CustomLoginView,
    profile_view,
    register,
)

app_name = "accounts"

urlpatterns = [
    path("register/", register, name="register"),

    path(
        "login/",
        CustomLoginView.as_view(),
        name="login",
    ),

    path(
        "logout/",
        LogoutView.as_view(next_page="core:home"),
        name="logout",
    ),

    path(
        "profile/",
        profile_view,
        name="profile",
    ),
]