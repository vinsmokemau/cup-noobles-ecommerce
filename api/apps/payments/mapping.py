"""Provider status to store state (SPEC.md 9.4).

`apply_payment_status` is the order side of a fetched payment: the amount guard, the
already-applied check, the late-payment case, then `apply_event`. The `Payment` row has been
recorded by the caller before this runs, so every refusal below still leaves the payment on file.

Extending the deadline of a pending voucher (9.5) belongs to T9.5; the voucher itself is already
stored on the payment.
"""

import logging

from django.db import transaction

from apps.orders.models import Order, OrderEvent
from apps.orders.state_machine import GuardFailed, apply_event
from apps.payments.base import NormalizedStatus, ProviderPayment
from apps.payments.models import Payment

logger = logging.getLogger(__name__)

ACTOR = "webhook"

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
        if event is None:  # pending, in_review, cancelled: nothing to do to the order
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
