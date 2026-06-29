"""
Root URL configuration.

All API routes are versioned under /api/v1/.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "api/v1/",
        include(
            [
                path("auth/", include("apps.authentication.urls")),
                path("", include("apps.profiles.urls")),
                path("interview/", include("apps.interviews.urls")),
                path("", include("apps.analytics.urls")),
            ]
        ),
    ),
]
