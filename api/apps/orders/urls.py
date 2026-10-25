from django.urls import path

from apps.orders import views

urlpatterns = [
    path("lookup/", views.OrderLookupView.as_view(), name="order-lookup"),
]
