from django.urls import path

from apps.shipping.devtools import views

urlpatterns = [
    path("track/<str:tracking_number>/", views.track, name="dev-carrier-track"),
    path(
        "track/<str:tracking_number>/<str:status>/",
        views.report,
        name="dev-carrier-report",
    ),
]
