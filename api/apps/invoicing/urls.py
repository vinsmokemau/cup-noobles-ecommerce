from django.urls import path

from apps.invoicing import views

urlpatterns = [
    path("cfdi-catalogs/", views.CfdiCatalogsView.as_view(), name="cfdi-catalogs"),
]
