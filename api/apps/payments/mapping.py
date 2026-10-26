"""Provider status to store state (SPEC.md 9.4).

`apply_payment_status` is the order side of a fetched payment: the amount guard, the
already-applied check, the late-payment case, then `apply_event`. The `Payment` row has been
recorded by the caller before this runs, so every refusal below still leaves the payment on file.

A `pending` OXXO or SPEI payment extends the order's deadline and its holds together (9.5, G48).
"""

import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.providers import payment_provider
from apps.inventory.models import InventoryReservation
from apps.orders.models import Order, OrderEvent
from apps.orders.state_machine import GuardFailed, apply_event
from apps.payments.base import NormalizedStatus, ProviderPayment
from apps.payments.models import Payment

logger = logging.getLogger(__name__)

ACTOR = "webhook"

# D6: an OXXO order stays open for this long after its voucher expires (9.5, §2.5).
OXXO_GRACE = timedelta(hours=2)

# `NormalizedStatus` -> `payment.status` (the 9.4 table, first two columns).
PAYMENT_STATUS: dict[NormalizedStatus, str] = {
    NormalizedStatus.APPROVED: "approved",
    NormalizedStatus.PENDING: "pending",
    NormalizedStatus.IN_REVIEW: "pending",
    NormalizedStatus.REJECTED: "rejected",
    NormalizedStatus.CANCELLED: "cancelled",
    NormalizedStatus.REFUNDED: "refunded",
    NormalizedStatus.PARTIALLY_REFUNDED: "partially_refunded",
    NormalizedStatus.CHARGED_BACK: "charged_back",
}

# `NormalizedStatus` -> order event (the third column). Absent: the status moves no order.
ORDER_EVENT: dict[NormalizedStatus, str] = {
    NormalizedStatus.APPROVED: "payment_approved",
    NormalizedStatus.REJECTED: "payment_rejected",
    NormalizedStatus.REFUNDED: "refund_issued",
    NormalizedStatus.PARTIALLY_REFUNDED: "partial_refund_issued",
}

# States that already reflect an approved payment (T2 happened).
_PAID_OR_LATER = ("paid", "preparing", "shipped", "delivered", "completed", "refunded")
# States in which an approved payment arrives too late (the stock was released, rule 3).
_CLOSED_UNPAID = ("expired", "cancelled")


def apply_payment_status(
    order: Order, payment: Payment, provider_payment: ProviderPayment
) -> None:
    """Apply rules 1 to 4 of 9.4 to `order`. Re-reads the order under its row lock, so a webhook
    and a reconciliation run on the same order serialise here (G14)."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        status = provider_payment.status

        if status is NormalizedStatus.CHARGED_BACK:
            _alert(
                order, payment, "the payment was charged back; a person must review it"
            )
            return
        event = ORDER_EVENT.get(status)
        if event is None:
            # pending, in_review, cancelled: the order state does not move
            if status in (NormalizedStatus.PENDING, NormalizedStatus.IN_REVIEW):
                _extend_for_method(order, payment, provider_payment)
            return

        # 1. Amount guard.
        if (
            status is NormalizedStatus.APPROVED
            and payment.amount_cents != order.total_cents
        ):
            _alert(
                order,
                payment,
                f"approved amount {payment.amount_cents} is not the order total "
                f"{order.total_cents}; the order was not moved",
            )
            return

        # 2. Already applied.
        if _already_applied(order, payment, status):
            OrderEvent.objects.create(
                order=order,
                from_state=order.state,
                to_state=order.state,
                event="webhook_no_op",
                actor=ACTOR,
                payload={"status": status.value, "payment_id": payment.pk},
            )
            return

        # 3. Late payment.
        if status is NormalizedStatus.APPROVED and order.state in _CLOSED_UNPAID:
            _alert(
                order,
                payment,
                f"late payment on an order that is {order.state}; refund it or fulfil it by hand",
            )
            return

        # 4. Otherwise the state machine decides.
        try:
            apply_event(
                order,
                event,
                actor=ACTOR,
                payment_id=payment.pk,
                amount_cents=payment.amount_cents,
                refunded_cents=payment.refunded_cents,
            )
        except GuardFailed as failed:
            if status is not NormalizedStatus.REJECTED:
                raise
            # A rejection after the deadline changes nothing: the expiry job (T5) owns the order.
            logger.warning(
                "Rejected payment ignored for order %s: %s", order.number, failed
            )


def method_deadline(
    method: str, voucher_expires_at: datetime | None, *, now: datetime
) -> datetime | None:
    """When an order paid with `method` must be paid by (9.5), or None when the checkout window
    already covers the method (card, wallet, Mercado Crédito)."""
    if method == "spei":
        return now + timedelta(hours=settings.RESERVATION_TTL_SPEI_HOURS)
    if method == "oxxo":
        # A voucher with no stated expiry gets the configured OXXO window from now.
        expiry = voucher_expires_at or now + timedelta(
            hours=settings.RESERVATION_TTL_OXXO_HOURS
        )
        return expiry + OXXO_GRACE
    return None


def _extend_for_method(
    order: Order, payment: Payment, provider_payment: ProviderPayment
) -> None:
    """Extend the deadline and the holds of a `pending_payment` order to the method's deadline.

    Caller holds the order row lock. Both move in the caller's transaction (G48), and neither
    ever moves earlier, so a later notification cannot shorten a window already granted.
    """
    deadline = method_deadline(
        provider_payment.method, provider_payment.voucher_expires_at, now=timezone.now()
    )
    if deadline is None:
        return
    if order.state in _CLOSED_UNPAID:
        # ADR-0046: the stock is gone, so the voucher is cancelled at the provider. A failure
        # propagates, so the webhook row is retried (G7).
        _alert(
            order,
            payment,
            f"a {provider_payment.method} voucher was generated for an order that is "
            f"{order.state}; its stock was released, so the voucher is being cancelled",
        )
        payment_provider().cancel_payment(provider_payment.provider_payment_id)
        return
    if order.state != "pending_payment":
        return
    if order.payment_deadline_at is None or order.payment_deadline_at < deadline:
        order.payment_deadline_at = deadline
        order.save(update_fields=["payment_deadline_at", "updated_at"])
    InventoryReservation.objects.filter(
        order=order,
        kind=InventoryReservation.Kind.STOCK,
        state=InventoryReservation.State.HELD,
        expires_at__lt=deadline,
    ).update(expires_at=deadline)


def _already_applied(order: Order, payment: Payment, status: NormalizedStatus) -> bool:
    if status is NormalizedStatus.APPROVED:
        return order.state in _PAID_OR_LATER
    if status is NormalizedStatus.REJECTED:
        # T4 leaves the order in `pending_payment`, so the audit trail is the only memory of it.
        return order.state != "pending_payment" or _recorded(
            order, payment, "payment_rejected"
        )
    if status is NormalizedStatus.REFUNDED:
        return order.state == "refunded" or _recorded(order, payment, "refund_issued")
    return _recorded(
        order, payment, "partial_refund_issued", refunded_cents=payment.refunded_cents
    )


def _recorded(order: Order, payment: Payment, event: str, **payload: int) -> bool:
    return order.events.filter(
        event=event,
        payload__payment_id=payment.pk,
        **{f"payload__{k}": v for k, v in payload.items()},
    ).exists()


def _alert(order: Order, payment: Payment, message: str) -> None:
    logger.error(
        "ALERT payment %s of order %s: %s",
        payment.provider_payment_id,
        order.number,
        message,
    )
