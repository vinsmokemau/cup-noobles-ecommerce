"""Root URL configuration. Each task adds its own routes."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from apps.core.views import HealthView
from apps.orders.views import CheckoutView

urlpatterns = [
    path("api/health/", HealthView.as_view(), name="health"),
    # T1.13b: the bare endpoint P1-V01 reads through the proxy; T5.5 extends the schema work.
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/catalog/", include("apps.catalog.urls")),
    path("api/cart/", include("apps.carts.urls")),
    path("api/checkout/", CheckoutView.as_view(), name="checkout"),
    path("api/orders/", include("apps.orders.urls")),
    path("api/webhooks/", include("apps.payments.urls")),
    path("api/postal-codes/", include("apps.shipping.urls")),
    path("admin/", admin.site.urls),
]
