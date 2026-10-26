from django.urls import path

from apps.payments import views

urlpatterns = [
    path(
        "payments/<str:provider>/",
        views.PaymentWebhookView.as_view(),
        name="payment-webhook",
    ),
]
