from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),

    path("", include("core.urls")),

    path("accounts/", include("accounts.urls")),

    path("carbon/", include("carbon.urls")),

    path("dashboard/", include("dashboard.urls")),

    path(
        "recommendations/",
        include("recommendations.urls"),
    ),
    
]