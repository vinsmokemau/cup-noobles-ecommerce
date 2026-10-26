from django.urls import path

from apps.payments.devtools import views

urlpatterns = [
    path(
        "checkout/<str:preference_id>/",
        views.checkout,
        name="dev-payments-checkout",
    ),
    path(
        "checkout/<str:preference_id>/<str:outcome>/",
        views.pay,
        name="dev-payments-pay",
    ),
    path(
        "voucher/<str:payment_id>/",
        views.voucher,
        name="dev-payments-voucher",
    ),
    path(
        "voucher/<str:payment_id>/<str:action>/",
        views.voucher_action,
        name="dev-payments-voucher-action",
    ),
]
