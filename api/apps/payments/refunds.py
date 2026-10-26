"""Refunds, always started by a human in the admin (SPEC.md 9.8, T9.8, REQ-032).

`refund_payment` is the only entry point. It rejects an amount above what is left before the
provider is called (the `payment_refund_le_amount` constraint is the backstop), calls
`provider.refund`, and applies `refund_issued` or `partial_refund_issued` through `apply_event`.

`refunded_cents` is a running total, never the latest amount (G46): the guards of T17 and T18
compare that total with the payment's amount, so two partial refunds in a row add up.
"""

from django.db import transaction

from apps.core.providers import payment_provider
from apps.orders.models import Order
from apps.orders.state_machine import apply_event
from apps.payments.models import Payment

# A refund can be made on a payment the provider approved and not yet returned in full.
REFUNDABLE_STATUSES = ("approved", "partially_refunded")


class RefundRejected(Exception):
    """The refund is refused before anything is sent to the provider or written."""


def remaining_cents(payment: Payment) -> int:
    return payment.amount_cents - payment.refunded_cents


def refundable_payments(order: Order) -> list[Payment]:
    """The order's payments that still have a balance to refund, oldest first."""
    return [
        payment
        for payment in order.payments.filter(status__in=REFUNDABLE_STATUSES).order_by(
            "id"
        )
        if remaining_cents(payment) > 0
    ]


def refund_payment(
    payment_id: int,
    *,
    actor: str,
    amount_cents: int | None = None,
    manual_note: str | None = None,
) -> Order:
    """Refund `amount_cents` of the payment, or what is left of it when `None`.

    Raises `RefundRejected` when the amount is not between 1 and the remaining balance, and
    `apps.payments.base.RefundNotSupported` when the provider cannot return this payment (OXXO
    cash). Pass `manual_note` to record a refund made outside the provider: the provider is not
    called and the note is required. Returns the order after the event.
    """
    note = None if manual_note is None else manual_note.strip()
    manual = note is not None
    if manual and not note:
        raise RefundRejected("Un reembolso manual necesita una nota.")
    with transaction.atomic():
        # The order row first, as `apply_event` does, so two refunds queue instead of crossing.
        order_id = Payment.objects.values_list("order_id", flat=True).get(pk=payment_id)
        order = Order.objects.select_for_update().get(pk=order_id)
        payment = Payment.objects.select_for_update().get(pk=payment_id)
        remaining = remaining_cents(payment)
        if payment.status not in REFUNDABLE_STATUSES or remaining <= 0:
            raise RefundRejected("El pago no tiene saldo por reembolsar.")
        amount = remaining if amount_cents is None else amount_cents
        if not 0 < amount <= remaining:
            raise RefundRejected(
                f"El monto debe estar entre 1 centavo y el saldo por reembolsar ({remaining} centavos)."
            )
        if not manual:
            amount = payment_provider().refund(payment, amount).amount_cents
        total = payment.refunded_cents + amount
        full = total == payment.amount_cents
        kwargs: dict[str, object] = {
            "payment_id": payment.pk,
            "refund_cents": amount,
            "refunded_cents": total,
        }
        if manual:
            kwargs["manual"] = True
            kwargs["note"] = note
        moved = apply_event(
            order,
            "refund_issued" if full else "partial_refund_issued",
            actor=actor,
            **kwargs,
        )
        Payment.objects.filter(pk=payment.pk).update(
            status="refunded" if full else "partially_refunded"
        )
    return moved
