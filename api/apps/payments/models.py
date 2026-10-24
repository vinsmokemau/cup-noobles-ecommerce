"""Payment tables (§4.4, `spec/schema.sql` PAYMENTS). Amounts are integer centavos (CR-01)."""

from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.catalog.models import json_default
from apps.core.db import NOW

PAYMENT_STATUSES = [
    "initiated",
    "pending",
    "authorized",
    "approved",
    "rejected",
    "cancelled",
    "refunded",
    "partially_refunded",
    "charged_back",
]


class Payment(models.Model):
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="payments",
        db_index=False,
    )
    provider = models.TextField(default="mercadopago", db_default="mercadopago")
    provider_preference_id = models.TextField(null=True, blank=True)
    provider_payment_id = models.TextField(null=True, blank=True)
    # 'credit_card', 'debit_card', 'oxxo', 'spei', 'wallet', 'account_money'
    method = models.TextField(null=True, blank=True)
    status = models.TextField(choices=[(status, status) for status in PAYMENT_STATUSES])
    amount_cents = models.IntegerField()
    refunded_cents = models.IntegerField(default=0, db_default=0)
    installments = models.IntegerField(null=True, blank=True)
    voucher_url = models.TextField(null=True, blank=True)  # OXXO ficha
    voucher_expires_at = models.DateTimeField(null=True, blank=True)
    raw = models.JSONField(default=dict, db_default=json_default({}))
    created_at = models.DateTimeField(default=timezone.now, db_default=NOW)
    updated_at = models.DateTimeField(auto_now=True, db_default=NOW)

    class Meta:
        db_table = "payment"
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=PAYMENT_STATUSES), name="payment_status_check"
            ),
            models.CheckConstraint(
                condition=Q(amount_cents__gte=0), name="payment_amount_cents_check"
            ),
            models.CheckConstraint(
                condition=Q(refunded_cents__gte=0), name="payment_refunded_cents_check"
            ),
            models.CheckConstraint(
                condition=Q(installments__isnull=True) | Q(installments__gt=0),
                name="payment_installments_check",
            ),
            models.CheckConstraint(
                condition=Q(refunded_cents__lte=F("amount_cents")),
                name="payment_refund_le_amount",
            ),
            models.UniqueConstraint(
                fields=["provider", "provider_payment_id"],
                condition=Q(provider_payment_id__isnull=False),
                name="payment_provider_payment_uq",
            ),
        ]
        indexes = [models.Index(fields=["order"], name="payment_order_idx")]


class WebhookEvent(models.Model):
    """Idempotency and forensics for provider callbacks. Insert first, process after."""

    provider = models.TextField()
    topic = models.TextField()  # 'payment', 'merchant_order'
    # The provider's notification (delivery) id, not the payment id (9.A rule 4).
    external_id = models.TextField()
    signature_ok = models.BooleanField()
    payload = models.JSONField()
    headers = models.JSONField(default=dict, db_default=json_default({}))
    received_at = models.DateTimeField(default=timezone.now, db_default=NOW)
    processed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.IntegerField(default=0, db_default=0)
    error = models.TextField(default="", db_default="", blank=True)

    class Meta:
        db_table = "webhook_event"
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "topic", "external_id"],
                name="webhook_event_provider_topic_external_id_key",
            )
        ]
        indexes = [
            models.Index(
                fields=["received_at"],
                condition=Q(processed_at__isnull=True),
                name="webhook_unprocessed_idx",
            )
        ]
