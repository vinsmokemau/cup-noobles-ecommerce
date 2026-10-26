"""Payment interface and value types shared by every adapter (SPEC.md §4.3, 9.1).

Each adapter maps its provider's vocabulary into `NormalizedStatus`; everything after that point
is shared. Callers obtain an adapter only through `providers.payment_provider()`.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from apps.orders.models import Order
    from apps.payments.models import Payment


class NormalizedStatus(StrEnum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    CHARGED_BACK = "charged_back"


@dataclass(frozen=True)
class CheckoutSession:
    preference_id: str
    url: str  # where the customer pays


@dataclass(frozen=True)
class RefundResult:
    refund_id: str
    amount_cents: int  # what this refund returned, in centavos


@dataclass(frozen=True)
class ProviderPayment:
    provider_payment_id: str
    external_reference: str  # order.public_id
    status: NormalizedStatus
    status_detail: str  # provider's raw detail, for logs and the admin
    method: str  # 'credit_card', 'debit_card', 'oxxo', 'spei', 'wallet'
    amount_cents: int
    refunded_cents: int
    installments: int | None
    voucher_url: str | None
    voucher_expires_at: datetime | None
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class WebhookRef:
    topic: str  # 'payment'
    notification_id: str  # -> webhook_event.external_id
    resource_id: str  # provider payment id


class PaymentNotFound(Exception): ...


class RefundNotSupported(Exception): ...


class PaymentProvider(Protocol):
    code: str  # 'mock' | 'mercadopago'; also the webhook path segment

    def create_checkout(self, order: "Order") -> CheckoutSession: ...

    def fetch_payment(self, provider_payment_id: str) -> ProviderPayment: ...

    def find_payments(self, external_reference: str) -> list[ProviderPayment]: ...

    def refund(self, payment: "Payment", amount_cents: int | None) -> RefundResult: ...

    def verify_webhook(
        self, headers: Mapping[str, str], body: bytes
    ) -> WebhookRef | None: ...
