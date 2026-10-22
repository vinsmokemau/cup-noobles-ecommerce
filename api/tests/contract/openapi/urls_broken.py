from django.urls import path

from tests.contract.openapi.fixture_views import BrokenView

urlpatterns = [path("api/broken/", BrokenView.as_view())]
