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
from apps.payments.money import cents_to_pesos

# outcome -> (status, method, back_urls key). A `None` status records no payment.
_OUTCOMES: dict[str, tuple[NormalizedStatus | None, str, str]] = {
    "card": (NormalizedStatus.APPROVED, "credit_card", "success"),
    "installments": (NormalizedStatus.APPROVED, "credit_card", "success"),
    "oxxo": (NormalizedStatus.PENDING, "oxxo", "pending"),
    "spei": (NormalizedStatus.PENDING, "spei", "pending"),
    "reject": (NormalizedStatus.REJECTED, "credit_card", "failure"),
    "expire": (None, "", "failure"),
}


def _mock() -> Any:
    """The active provider when it is the mock; the simulator has nothing to show otherwise."""
    provider = providers.payment_provider()
    if provider.code != "mock":
        raise Http404
    return provider


def _money(cents: int) -> str:
    return f"${cents_to_pesos(cents):,.2f} MXN"


def _fake_digits(payment_id: str, length: int) -> str:
    """Digits derived from the mock payment id, so a voucher is stable across page loads."""
    return str(int(payment_id.removeprefix("mock_pay_"), 16) % 10**length).zfill(length)


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
    if preference is None or outcome not in _OUTCOMES:
        raise Http404
    status, method, back_url = _OUTCOMES[outcome]
    installments = None
    if outcome == "installments":
        try:
            installments = int(request.POST.get("installments", ""))
        except ValueError:
            return HttpResponseBadRequest("Plazo no disponible")
        if installments not in settings.PAYMENT_INSTALLMENT_OPTIONS:
            return HttpResponseBadRequest("Plazo no disponible")
    if status is not None:
        payment_id = provider.record_payment(
            preference_id,
            status=status,
            method=method,
            installments=installments,
            status_detail="accredited" if status == NormalizedStatus.APPROVED else "",
        )
        if status == NormalizedStatus.PENDING:
            site_url = str(settings.SITE_URL).rstrip("/")
            fields: dict[str, Any] = {
                "voucher_url": f"{site_url}/dev/payments/voucher/{payment_id}/",
                "voucher_expires_at": preference["expires_at"],
            }
            if method == "oxxo":
                fields["reference"] = _fake_digits(payment_id, 14)
            else:
                fields["clabe"] = _fake_digits(payment_id, 18)
            provider.update_payment(payment_id, **fields)
        provider.queue_notification(payment_id)
    return redirect(preference["back_urls"][back_url])


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
    if payment.status == NormalizedStatus.PENDING:
        if action == "received":
            provider.update_payment(
                payment_id,
                status=NormalizedStatus.APPROVED.value,
                status_detail="accredited",
            )
        else:
            provider.cancel_payment(payment_id)
        provider.queue_notification(payment_id)
    return redirect("dev-payments-voucher", payment_id=payment_id)
