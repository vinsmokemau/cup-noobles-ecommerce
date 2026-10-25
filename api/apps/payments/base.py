"""Payment interface and value types shared by every adapter (SPEC.md §4.3, 9.1).

T8.10 adds the two methods the mock builds first, with the types they return. T9.1 completes the
Protocol (`fetch_payment`, `find_payments`, `verify_webhook`) and adds the other value types.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from apps.orders.models import Order
    from apps.payments.models import Payment


@dataclass(frozen=True)
class CheckoutSession:
    preference_id: str
    url: str  # where the customer pays


@dataclass(frozen=True)
class RefundResult:
    refund_id: str
    amount_cents: int  # what this refund returned, in centavos


class PaymentProvider(Protocol):
    code: str  # 'mock' | 'mercadopago'; also the webhook path segment

    def create_checkout(self, order: "Order") -> CheckoutSession: ...

    def refund(self, payment: "Payment", amount_cents: int | None) -> RefundResult: ...
