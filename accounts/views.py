from django.contrib import messages
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required

from .forms import (
    CustomAuthenticationForm,
    CustomUserCreationForm,
    UserLocationForm,
)

from carbon.models import UserLocation

from django.contrib.auth import login
from django.contrib.auth.views import LoginView

def register(request):
    """
    Register a new user.
    """

    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Account created successfully. You can now log in.",
            )

            return redirect("accounts:login")

    else:
        form = CustomUserCreationForm()

    context = {
        "form": form,
    }

    return render(
        request,
        "accounts/register.html",
        context,
    )

class CustomLoginView(LoginView):
    """
    Display and process the login form.
    """

    template_name = "accounts/login.html"
    authentication_form = CustomAuthenticationForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(
            self.request,
            "Welcome back!",
        )
        return super().form_valid(form)

    def get_success_url(self):
        return "/"

@login_required
def profile_view(request):
    """
    Display and update the logged-in user's profile and
    benchmarking location.
    """

    try:
        location = request.user.location
    except UserLocation.DoesNotExist:
        location = None

    if request.method == "POST":
        form = UserLocationForm(
            request.POST,
            instance=location,
        )

        if form.is_valid():
            saved_location = form.save(commit=False)
            saved_location.user = request.user
            saved_location.save()

            messages.success(
                request,
                "Benchmarking location updated successfully.",
            )

            return redirect("accounts:profile")

    else:
        form = UserLocationForm(instance=location)

    return render(
        request,
        "accounts/profile.html",
        {
            "form": form,
            "location": location,
            "districts_by_state": form.districts_by_state,
        },
    )