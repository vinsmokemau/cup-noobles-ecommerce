from django.urls import path

from apps.core.devtools import views

urlpatterns = [
    path("prelaunch/", views.prelaunch, name="dev-test-prelaunch"),
    path("inventory/<str:sku>/", views.inventory, name="dev-test-inventory"),
    path("orders/", views.orders, name="dev-test-orders"),
]
