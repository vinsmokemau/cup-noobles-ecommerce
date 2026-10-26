"""The order state machine (SPEC.md 8.A, REQ-020, CR-09, CR-10).

`TRANSITIONS` holds the Release 1 rows of the 8.A table. `apply_event` is the only code that
assigns `order.state`: it takes the row lock, looks the event up, runs the guard and the side
effects, and writes exactly one `order_event`. Anything not in `TRANSITIONS` is illegal.

Side effects that need code from a later task are named in the row's comment and added there:
the CFDI flag of T17 and T18 (T9.14).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.providers import payment_provider
from apps.inventory import services as inventory
from apps.notifications.outbox import enqueue_email
from apps.orders.models import Order, OrderEvent, Shipment
from apps.orders.pricing import compute_totals
from apps.payments.models import Payment


class IllegalTransition(Exception):
    """The event is not in `TRANSITIONS` for the order's state (CR-10)."""

    def __init__(self, from_state: str, event: str) -> None:
        self.from_state = from_state
        self.event = event
        super().__init__(f"Event {event!r} is illegal from state {from_state!r}")


class GuardFailed(Exception):
    """The row exists but its guard does not hold. The order is unchanged."""

    def __init__(self, event: str, reason: str) -> None:
        self.event = event
        self.reason = reason
        super().__init__(f"Guard of {event!r} failed: {reason}")


Guard = Callable[..., None]
Effects = Callable[..., None]


@dataclass(frozen=True)
class Transition:
    to_state: str | Callable[[Order], str]
    guard: Guard
    effects: Effects

    def target(self, order: Order) -> str:
        return self.to_state(order) if callable(self.to_state) else self.to_state


def _no_guard(order: Order, **kwargs: Any) -> None:
    return None


def _no_effects(order: Order, **kwargs: Any) -> None:
    return None


def _fail(event: str, reason: str) -> GuardFailed:
    return GuardFailed(event, reason)


# --- guards -----------------------------------------------------------------------------


def _guard_target_complete(order: Order, **kwargs: Any) -> None:
    if order.fulfillment_method == Order.FulfillmentMethod.PICKUP:
        complete = order.pickup_location_id is not None
    else:
        complete = bool(order.shipping_address)
    if not complete:
        raise _fail("checkout_submitted", "the fulfillment target is incomplete")


def _guard_checkout_ready(order: Order, **kwargs: Any) -> None:
    """T1: the target is complete, every line is available, and the totals add up."""
    _guard_target_complete(order)
    lines = list(order.lines.select_related("variant").order_by("id"))
    wanted = [(line.variant, line.quantity) for line in lines if line.variant]
    if not lines or len(wanted) != len(lines):
        raise _fail("checkout_submitted", "the order has no purchasable lines")
    inventory.lock_variants(variant.pk for variant, _ in wanted)
    if inventory.shortfalls(wanted):
        raise _fail("checkout_submitted", "a line is not available")
    totals = compute_totals(lines, order.shipping_cents, order.discount_cents)
    if (totals.subtotal_cents, totals.total_cents, totals.tax_included_cents) != (
        order.subtotal_cents,
        order.total_cents,
        order.tax_included_cents,
    ):
        raise _fail("checkout_submitted", "the totals are not the recomputed totals")


def _guard_payment_matches(order: Order, **kwargs: Any) -> None:
    if kwargs.get("amount_cents") != order.total_cents:
        raise _fail("payment_approved", "the amount is not the order total")
    if order.has_preorder_items or order.lines.filter(is_preorder=True).exists():
        raise _fail("payment_approved", "the order has pre-order lines")


def _guard_before_deadline(order: Order, **kwargs: Any) -> None:
    deadline = order.payment_deadline_at
    if deadline is not None and deadline <= timezone.now():
        raise _fail("payment_rejected", "the payment deadline has passed")


def _guard_deadline_passed(order: Order, **kwargs: Any) -> None:
    deadline = order.payment_deadline_at
    if deadline is None or deadline >= timezone.now():
        raise _fail("deadline_passed", "the payment deadline has not passed")


def _guard_delivery(order: Order, **kwargs: Any) -> None:
    if order.fulfillment_method != Order.FulfillmentMethod.DELIVERY:
        raise _fail("auto", "the order is not a delivery order")


def _guard_shipment_with_tracking(order: Order, **kwargs: Any) -> None:
    if not order.shipments.exclude(tracking_number="").exists():
        raise _fail("shipment_created", "no shipment with a tracking number")


def _guard_cancel_reason(order: Order, **kwargs: Any) -> None:
    reason = kwargs.get("cancel_reason")
    if not isinstance(reason, str) or not reason.strip():
        raise _fail("cancelled_by_staff", "cancel_reason is required")


def _refund_payment(order: Order, event: str, kwargs: dict[str, Any]) -> Payment:
    payment_id = kwargs.get("payment_id")
    refunded = kwargs.get("refunded_cents")
    if not isinstance(payment_id, int) or not isinstance(refunded, int):
        raise _fail(event, "payment_id and refunded_cents of this order are required")
    payment = (
        Payment.objects.select_for_update().filter(pk=payment_id, order=order).first()
    )
    if payment is None:
        raise _fail(event, "payment_id and refunded_cents of this order are required")
    return payment


def _guard_full_refund(order: Order, **kwargs: Any) -> None:
    payment = _refund_payment(order, "refund_issued", kwargs)
    if kwargs["refunded_cents"] != payment.amount_cents:
        raise _fail("refund_issued", "the refund is not the full payment")


def _guard_partial_refund(order: Order, **kwargs: Any) -> None:
    payment = _refund_payment(order, "partial_refund_issued", kwargs)
    if not 0 < kwargs["refunded_cents"] < payment.amount_cents:
        raise _fail("partial_refund_issued", "the refund is not a part of the payment")


# --- side effects -----------------------------------------------------------------------


def _effects_checkout_submitted(order: Order, **kwargs: Any) -> None:
    """T1. Prices were frozen and the number assigned when the draft was created (T8.2)."""
    now = timezone.now()
    ttl = timedelta(minutes=settings.RESERVATION_TTL_CARD_MINUTES)
    order.placed_at = now
    order.payment_deadline_at = now + ttl
    lines = order.lines.select_related("variant").order_by("id")
    wanted = [(line.variant, line.quantity) for line in lines if line.variant]
    inventory.reserve(order, wanted, ttl=ttl)
    session = payment_provider().create_checkout(order)
    # The attempt is kept so `checkout_url` can be handed back and the payment found later.
    Payment.objects.create(
        order=order,
        provider=payment_provider().code,
        provider_preference_id=session.preference_id,
        status="initiated",
        amount_cents=order.total_cents,
        raw={"checkout_url": session.url},
    )


def _effects_payment_approved(order: Order, **kwargs: Any) -> None:
    inventory.commit_reservations(order)
    order.paid_at = timezone.now()
    enqueue_email(
        order.email,
        "order_confirmation",
        {"order_number": order.number},
        order=order,
        dedupe_key=f"order_confirmation:{order.pk}",
    )


def _effects_deadline_passed(order: Order, **kwargs: Any) -> None:
    inventory.release_reservations(order, reason="payment deadline passed")
    enqueue_email(
        order.email,
        "order_expired",
        {"order_number": order.number},
        order=order,
        dedupe_key=f"order_expired:{order.pk}",
    )


def _effects_cancelled_by_customer(order: Order, **kwargs: Any) -> None:
    inventory.release_reservations(order, reason="cancelled by customer")
    order.cancelled_at = timezone.now()


def _effects_shipment_created(order: Order, **kwargs: Any) -> None:
    order.shipped_at = timezone.now()
    shipment = order.shipments.exclude(tracking_number="").order_by("-id").first()
    assert shipment is not None  # the guard found one
    enqueue_email(
        order.email,
        "order_shipped",
        {
            "order_number": order.number,
            "carrier": shipment.carrier,
            "tracking_number": shipment.tracking_number,
            "tracking_url": shipment.tracking_url,
        },
        order=order,
        dedupe_key=f"order_shipped:{order.pk}",
    )


def _effects_marked_delivered(order: Order, **kwargs: Any) -> None:
    Shipment.objects.filter(order=order, delivered_at__isnull=True).update(
        delivered_at=timezone.now()
    )


def _effects_auto_after_7d(order: Order, **kwargs: Any) -> None:
    order.completed_at = timezone.now()


def _effects_cancelled_by_staff(order: Order, **kwargs: Any) -> None:
    order.cancel_reason = kwargs["cancel_reason"].strip()
    order.cancelled_at = timezone.now()
    inventory.return_stock(order, note="cancelled by staff")
    # Refund what was paid, in full (T16, ADR-0041). An order with no approved payment has
    # nothing to refund.
    for payment in order.payments.filter(status="approved").select_for_update():
        result = payment_provider().refund(payment, None)
        payment.refunded_cents += result.amount_cents
        payment.status = "refunded"
        payment.save(update_fields=["refunded_cents", "status", "updated_at"])


def _effects_refund(order: Order, **kwargs: Any) -> None:
    Payment.objects.filter(pk=kwargs["payment_id"], order=order).update(
        refunded_cents=kwargs["refunded_cents"]
    )


# --- the table --------------------------------------------------------------------------

TRANSITIONS: dict[tuple[str, str], Transition] = {}


def _row(
    sources: tuple[str, ...],
    event: str,
    to_state: str | Callable[[Order], str],
    guard: Guard = _no_guard,
    effects: Effects = _no_effects,
) -> None:
    for source in sources:
        TRANSITIONS[(source, event)] = Transition(to_state, guard, effects)


# The states an order passes through after payment and before it is closed. A refund can
# land in any of them; the terminal states and `partially_refunded` are G26 and G27.
POST_PAID = ("paid", "preparing", "shipped", "delivered")

# T1 (the number and the frozen prices are set when the draft is created, T8.2)
_row(
    ("draft",),
    "checkout_submitted",
    "pending_payment",
    _guard_checkout_ready,
    _effects_checkout_submitted,
)
# T2
_row(
    ("pending_payment",),
    "payment_approved",
    "paid",
    _guard_payment_matches,
    _effects_payment_approved,
)
# T4
_row(
    ("pending_payment",),
    "payment_rejected",
    "pending_payment",
    _guard_before_deadline,
)
# T5
_row(
    ("pending_payment",),
    "deadline_passed",
    "expired",
    _guard_deadline_passed,
    _effects_deadline_passed,
)
# T6
_row(
    ("pending_payment",),
    "cancelled_by_customer",
    "cancelled",
    effects=_effects_cancelled_by_customer,
)
# T7 (T8 shares the key in Release 2 and branches in `to_state`)
_row(("paid",), "auto", "preparing", _guard_delivery)
# T10
_row(
    ("preparing",),
    "shipment_created",
    "shipped",
    _guard_shipment_with_tracking,
    _effects_shipment_created,
)
# T11
_row(("shipped",), "marked_delivered", "delivered", effects=_effects_marked_delivered)
# T12
_row(("delivered",), "auto_after_7d", "completed", effects=_effects_auto_after_7d)
# T16 from paid and preparing
_row(
    ("paid", "preparing"),
    "cancelled_by_staff",
    "cancelled",
    _guard_cancel_reason,
    _effects_cancelled_by_staff,
)
# T17 (the CFDI flag arrives with T9.14)
_row(POST_PAID, "refund_issued", "refunded", _guard_full_refund, _effects_refund)
# T18 (the CFDI flag arrives with T9.14)
_row(
    POST_PAID,
    "partial_refund_issued",
    "partially_refunded",
    _guard_partial_refund,
    _effects_refund,
)


@transaction.atomic
def apply_event(
    order_id: int | Order, event: str, *, actor: str = "system", **kwargs: Any
) -> Order:
    """Move an order by one event. Takes the id, or an order whose id is used: the row is
    always re-read under the lock, so a stale instance cannot overwrite a newer state."""
    pk = order_id.pk if isinstance(order_id, Order) else order_id
    order = Order.objects.select_for_update().get(pk=pk)
    t = TRANSITIONS.get((order.state, event))
    if t is None:
        raise IllegalTransition(order.state, event)
    t.guard(order, **kwargs)
    from_state = order.state
    order.state = t.target(order)
    t.effects(order, **kwargs)
    order.save()
    OrderEvent.objects.create(
        order=order,
        from_state=from_state,
        to_state=order.state,
        event=event,
        actor=actor,
        payload=kwargs,
    )
    return order
