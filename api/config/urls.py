"""Root URL configuration. Each task adds its own routes."""

from django.urls import path

from apps.core.views import HealthView

urlpatterns = [
    path("api/health/", HealthView.as_view(), name="health"),
]
