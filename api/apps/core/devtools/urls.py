from django.urls import path

from apps.core.devtools import views

urlpatterns = [
    path("prelaunch/", views.prelaunch, name="dev-test-prelaunch"),
]
