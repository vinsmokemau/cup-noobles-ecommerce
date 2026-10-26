"""The payment contract suite's driver (SPEC.md 9.13, §4.6 "Contract — providers").

Scenarios are written once, against `PaymentDriver`. `MockDriver` plays the customer on the mock
provider's side and delivers the queued notifications through the real webhook endpoint; the
Mercado Pago sandbox driver arrives in Phase 16. Everything past the provider (the endpoint,
`webhook_event` rows, the mapping, the state machine) is the code production runs.
"""

from enum import StrEnum
from typing import Any, Protocol

from rest_framework.test import APIClient

from apps.core import providers
from apps.orders.models import Order
from apps.payments.base import CheckoutSession
from apps.payments.devtools import delivery, outcomes
from apps.payments.models import Payment


class Outcome(StrEnum):
    """What the customer does on the provider's page, or the provider does afterwards."""

    APPROVED = "approved"
    APPROVED_IN_INSTALLMENTS = "approved_in_installments"
    OXXO_VOUCHER = "oxxo_voucher"
    SPEI_TRANSFER = "spei_transfer"
    REJECTED = "rejected"
    ABANDONED = "abandoned"  # nothing is paid, nothing is sent
    VOUCHER_PAID = "voucher_paid"  # needs `payment_id`
    VOUCHER_LAPSED = "voucher_lapsed"  # needs `payment_id`


class PaymentDriver(Protocol):
    name: str

    def supports(self, scenario: str) -> bool | str:
        """True, or why the scenario can't be driven."""
        ...

    def checkout(self, order: Order) -> CheckoutSession: ...

    def complete(self, session: CheckoutSession, outcome: Outcome, **opts: Any) -> str:
        """Play `outcome`; returns the provider's payment id ("" when nothing was paid)."""
        ...

    def deliver_pending_notifications(self) -> None: ...


# Scenario -> outcome path -> installments etc. all map onto the simulator's buttons (9.10).
_BUTTONS = {
    Outcome.APPROVED: "card",
    Outcome.APPROVED_IN_INSTALLMENTS: "installments",
    Outcome.OXXO_VOUCHER: "oxxo",
    Outcome.SPEI_TRANSFER: "spei",
    Outcome.REJECTED: "reject",
    Outcome.ABANDONED: "expire",
}


class MockDriver:
    name = "mock"

    def __init__(self) -> None:
        self.client = APIClient()

    def supports(self, scenario: str) -> bool | str:
        return True

    def checkout(self, order: Order) -> CheckoutSession:
        """The session the order's checkout opened; a new one when it has none (a retry)."""
        provider = providers.payment_provider()
        payment = (
            Payment.objects.filter(order=order, provider_preference_id__isnull=False)
            .order_by("-id")
            .first()
        )
        if payment is None or payment.status != "initiated":
            return provider.create_checkout(order)
        preference = payment.provider_preference_id
        assert preference is not None
        return CheckoutSession(
            preference_id=preference, url=str(payment.raw["checkout_url"])
        )

    def complete(self, session: CheckoutSession, outcome: Outcome, **opts: Any) -> str:
        provider: Any = providers.payment_provider()
        if outcome in (Outcome.VOUCHER_PAID, Outcome.VOUCHER_LAPSED):
            payment_id: str = opts["payment_id"]
            outcomes.settle_voucher(
                provider,
                payment_id,
                "received" if outcome is Outcome.VOUCHER_PAID else "expired",
            )
            return payment_id
        preference = provider.get_preference(session.preference_id)
        assert preference is not None, session.preference_id
        return (
            outcomes.record_outcome(
                provider,
                preference,
                _BUTTONS[outcome],
                installments=opts.get("installments"),
                amount_cents=opts.get("amount_cents"),
                notify=opts.get("notify", True),
            )
            or ""
        )

    def deliver_pending_notifications(self) -> None:
        def send(body: bytes, headers: dict[str, str]) -> int:
            return self.client.post(
                delivery.WEBHOOK_PATH,
                data=body,
                content_type="application/json",
                headers=headers,
            ).status_code

        result = delivery.deliver(send, honour_delay=False)
        assert result.failed == 0, (
            f"the webhook refused {result.failed} notification(s)"
        )
