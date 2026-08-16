from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .services.dashboard import DashboardService


@login_required
def dashboard(request):
    """
    Render the authenticated user's CarbonIQ dashboard.
    """

    dashboard_data = DashboardService.get_dashboard_data(
        request.user
    )

    return render(
        request,
        "dashboard/dashboard.html",
        dashboard_data,
    )