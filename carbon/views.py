from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from carbon.models import ActivityCategory, CarbonActivity
from .forms import ActivityEntryFormSet
from .services.submission import CarbonSubmissionService
from recommendations.services.integration import (
    refresh_user_recommendations,
)

@login_required
def calculator(request):
    """
    Display and process the CarbonIQ carbon calculator.
    """

    if request.method == "POST":
        formset = ActivityEntryFormSet(request.POST)

        if formset.is_valid():
            entries_data = [
                {
                    "category": form.cleaned_data["category"],
                    "quantity": form.cleaned_data["quantity"],
                }
                for form in formset.forms
                if form.cleaned_data
            ]

            activity = CarbonSubmissionService.create_submission(
                user=request.user,
                entries_data=entries_data,
            )
            refresh_user_recommendations(request.user)
            return redirect(
                "carbon:result",
                pk=activity.pk,
            )

    else:
        formset = ActivityEntryFormSet()

    category_units = {
        str(category.pk): category.unit
        for category in ActivityCategory.objects.filter(
            is_active=True
        )
    }
    
    return render(
        request,
        "carbon/calculator.html",
        {
            "formset": formset,
            "category_units": category_units,
        },
    )

@login_required
def result(request, pk):
    """
    Display the calculated carbon footprint for a user's submission.
    """

    activity = get_object_or_404(
        CarbonActivity.objects.select_related("carbon_footprint").prefetch_related(
            "entries__category"
        ),
        pk=pk,
        user=request.user,
    )

    return render(
        request,
        "carbon/result.html",
        {
            "activity": activity,
            "footprint": activity.carbon_footprint,
            "entries": activity.entries.all(),
        },
    )