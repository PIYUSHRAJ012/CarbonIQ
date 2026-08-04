from django.contrib import messages
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required

from .forms import (
    CustomAuthenticationForm,
    CustomUserCreationForm,
)

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
    Display the logged-in user's profile.
    """
    return render(
        request,
        "accounts/profile.html",
    )