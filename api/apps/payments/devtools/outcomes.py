"""What a customer can do on the provider's page, recorded in the mock store (SPEC.md 9.10, 9.12a).

The simulator buttons and the `mock_payments` commands share this code, so a command does exactly
what its button does.
"""

from typing import Any

from django.conf import settings

from apps.payments.base import NormalizedStatus

# outcome -> (status, method, back_urls key). A `None` status records no payment.
OUTCOMES: dict[str, tuple[NormalizedStatus | None, str, str]] = {
    "card": (NormalizedStatus.APPROVED, "credit_card", "success"),
    "installments": (NormalizedStatus.APPROVED, "credit_card", "success"),
    "oxxo": (NormalizedStatus.PENDING, "oxxo", "pending"),
    "spei": (NormalizedStatus.PENDING, "spei", "pending"),
    "reject": (NormalizedStatus.REJECTED, "credit_card", "failure"),
    "expire": (None, "", "failure"),
}


def _fake_digits(payment_id: str, length: int) -> str:
    """Digits derived from the mock payment id, so a voucher is stable across page loads."""
    return str(int(payment_id.removeprefix("mock_pay_"), 16) % 10**length).zfill(length)


def record_outcome(
    provider: Any,
    preference: dict[str, Any],
    outcome: str,
    *,
    installments: int | None = None,
    amount_cents: int | None = None,
    notify: bool = True,
) -> str | None:
    """Record `outcome` for `preference`; returns the `mock_pay_…` id, or `None` for `expire`.

    With `notify=False` nothing is queued, so only reconciliation can discover the payment.
    """
    status, method, _ = OUTCOMES[outcome]
    if status is None:
        return None
    payment_id: str = provider.record_payment(
        preference["id"],
        status=status,
        method=method,
        amount_cents=amount_cents,
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
    if notify:
        provider.queue_notification(payment_id)
    return payment_id


def settle_voucher(provider: Any, payment_id: str, action: str) -> None:
    """Complete (`received`) or lapse (`expired`) a pending voucher and queue a notification.

    A voucher that is no longer pending is left alone.
    """
    payment = provider.fetch_payment(payment_id)
    if payment.status != NormalizedStatus.PENDING:
        return
    if action == "received":
        provider.update_payment(
            payment_id,
            status=NormalizedStatus.APPROVED.value,
            status_detail="accredited",
        )
    else:
        provider.cancel_payment(payment_id)
    provider.queue_notification(payment_id)
