from django.urls import path

from tests.contract.openapi.fixture_views import PingView

urlpatterns = [path("api/ping/", PingView.as_view())]
