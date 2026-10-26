"""The payment simulator pages (SPEC.md 9.10). Routed only when `DEV_TOOLS_ENABLED`.

The pages record what a customer did on the provider's page in the mock store and queue a
notification (ids only). They never call the webhook: `mock_payments deliver` does (9.11).
"""

from typing import Any

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.core import providers
from apps.payments.base import NormalizedStatus, PaymentNotFound
from apps.payments.devtools import outcomes
from apps.payments.money import cents_to_pesos


def _mock() -> Any:
    """The active provider when it is the mock; the simulator has nothing to show otherwise."""
    provider = providers.payment_provider()
    if provider.code != "mock":
        raise Http404
    return provider


def _money(cents: int) -> str:
    return f"${cents_to_pesos(cents):,.2f} MXN"


@require_GET
def checkout(request: HttpRequest, preference_id: str) -> HttpResponse:
    preference = _mock().get_preference(preference_id)
    if preference is None:
        raise Http404
    lines = [
        {
            "name": line["name"],
            "quantity": line["quantity"],
            "unit_price": _money(line["unit_price_cents"]),
        }
        for line in preference["lines"]
    ]
    return render(
        request,
        "payments_devtools/checkout.html",
        {
            "preference_id": preference_id,
            "order_number": preference["order_number"],
            "lines": lines,
            "total": _money(preference["total_cents"]),
            "installment_options": settings.PAYMENT_INSTALLMENT_OPTIONS,
        },
    )


@require_POST
def pay(request: HttpRequest, preference_id: str, outcome: str) -> HttpResponse:
    provider = _mock()
    preference = provider.get_preference(preference_id)
    if preference is None or outcome not in outcomes.OUTCOMES:
        raise Http404
    installments = None
    if outcome == "installments":
        try:
            installments = int(request.POST.get("installments", ""))
        except ValueError:
            return HttpResponseBadRequest("Plazo no disponible")
        if installments not in settings.PAYMENT_INSTALLMENT_OPTIONS:
            return HttpResponseBadRequest("Plazo no disponible")
    outcomes.record_outcome(provider, preference, outcome, installments=installments)
    return redirect(preference["back_urls"][outcomes.OUTCOMES[outcome][2]])


@require_GET
def voucher(request: HttpRequest, payment_id: str) -> HttpResponse:
    provider = _mock()
    try:
        payment = provider.fetch_payment(payment_id)
    except PaymentNotFound:
        raise Http404 from None
    if payment.method not in ("oxxo", "spei"):
        raise Http404
    preference = provider.get_preference(payment.raw["preference_id"])
    return render(
        request,
        "payments_devtools/voucher.html",
        {
            "payment_id": payment_id,
            "method": payment.method,
            "status": payment.status.value,
            "pending": payment.status == NormalizedStatus.PENDING,
            "order_number": preference["order_number"] if preference else "",
            "total": _money(payment.amount_cents),
            "expires_at": payment.voucher_expires_at,
            "reference": payment.raw.get("reference"),
            "clabe": payment.raw.get("clabe"),
        },
    )


@require_POST
def voucher_action(request: HttpRequest, payment_id: str, action: str) -> HttpResponse:
    if action not in ("received", "expired"):
        raise Http404
    provider = _mock()
    try:
        payment = provider.fetch_payment(payment_id)
    except PaymentNotFound:
        raise Http404 from None
    if payment.method not in ("oxxo", "spei"):
        raise Http404
    outcomes.settle_voucher(provider, payment_id, action)
    return redirect("dev-payments-voucher", payment_id=payment_id)
