"""Provider status to store state (SPEC.md 9.4).

T9.3 records every fetched payment and calls `apply_payment_status`, which is a stub until T9.4
fills it with the amount guard, the already-applied check, the late-payment case and the order
events. Until then a webhook stores the payment and moves no order.
"""

from apps.orders.models import Order
from apps.payments.base import NormalizedStatus, ProviderPayment
from apps.payments.models import Payment

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


def apply_payment_status(
    order: Order, payment: Payment, provider_payment: ProviderPayment
) -> None:
    """The order side of a fetched payment. Filled in by T9.4."""
