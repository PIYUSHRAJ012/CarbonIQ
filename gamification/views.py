from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .models import Challenge
from .services.challenges import join_challenge


@login_required
@require_POST
def join_challenge_view(request, challenge_id):
    """
    Enrol the authenticated user in an available sustainability
    challenge.

    Only the challenge identifier is accepted from the request.
    User identity and challenge progress remain server-controlled.
    """

    challenge = get_object_or_404(
        Challenge,
        pk=challenge_id,
    )

    try:
        join_challenge(
            request.user,
            challenge,
        )
    except ValueError as exc:
        messages.error(
            request,
            str(exc),
        )
    else:
        messages.success(
            request,
            f"You joined the challenge: {challenge.title}",
        )

    return redirect("dashboard:home")