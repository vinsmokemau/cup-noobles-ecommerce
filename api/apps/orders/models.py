"""Order tables (§4.4, `spec/schema.sql` ORDERS and FULFILLMENT).

Money is integer centavos of MXN (CR-01). `state` changes only through `apply_event` (CR-04);
`order_event` is the append-only audit trail. The per-year order-number sequences (G5) are
created by the service on first use and are not part of the schema.
"""

import uuid

from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.catalog.models import json_default
from apps.core.db import GEN_RANDOM_UUID, NOW
from apps.core.fields import CIEmailField, FixedCharField

ORDER_STATES = [
    "draft",
    "pending_payment",
    "paid",
    "awaiting_stock",
    "preparing",
    "ready_for_pickup",
    "shipped",
    "delivered",
    "picked_up",
    "completed",
    "cancelled",
    "expired",
    "refunded",
    "partially_refunded",
]


class Order(models.Model):
    class FulfillmentMethod(models.TextChoices):
        DELIVERY = "delivery"
        PICKUP = "pickup"

    public_id = models.UUIDField(
        default=uuid.uuid4, db_default=GEN_RANDOM_UUID, unique=True, editable=False
    )
    number = models.TextField()  # 'CN-2026-000123'; unique, see `order_number_key`
    customer = models.ForeignKey(
        "accounts.Customer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_index=False,
    )
    email = CIEmailField()  # always set; guest checkout is supported
    phone = models.TextField(default="", db_default="", blank=True)
    state = models.TextField(choices=[(state, state) for state in ORDER_STATES])
    fulfillment_method = models.TextField(choices=FulfillmentMethod.choices)
    pickup_location = models.ForeignKey(
        "inventory.Location",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        db_index=False,
    )
    # Frozen snapshot. Never a FK to address: the customer may edit or delete it.
    shipping_address = models.JSONField(null=True, blank=True)
    shipping_rate_name = models.TextField(default="", db_default="", blank=True)
    subtotal_cents = models.IntegerField()
    shipping_cents = models.IntegerField(default=0, db_default=0)
    discount_cents = models.IntegerField(default=0, db_default=0)
    total_cents = models.IntegerField()
    # IVA contained within total_cents (prices are IVA-inclusive, A2).
    tax_included_cents = models.IntegerField(default=0, db_default=0)
    currency = FixedCharField(max_length=3, default="MXN", db_default="MXN")
    has_preorder_items = models.BooleanField(default=False, db_default=False)
    earliest_release_date = models.DateField(null=True, blank=True)
    payment_deadline_at = models.DateTimeField(null=True, blank=True)
    pickup_deadline_at = models.DateTimeField(null=True, blank=True)
    customer_note = models.TextField(default="", db_default="", blank=True)
    internal_note = models.TextField(default="", db_default="", blank=True)
    cancel_reason = models.TextField(default="", db_default="", blank=True)
    # Checkout idempotency (G3, ADR-0030). The key is scoped to the cart token; the
    # fingerprint is the SHA-256 hex digest of the canonical request body.
    cart_token = models.UUIDField(null=True, blank=True)
    idempotency_key = models.TextField(null=True, blank=True)
    idempotency_fingerprint = models.TextField(null=True, blank=True)
    placed_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_default=NOW)
    updated_at = models.DateTimeField(auto_now=True, db_default=NOW)

    class Meta:
        db_table = "order"
        constraints = [
            # A constraint, not `unique=True`: Django would add a `_like` index the schema lacks.
            models.UniqueConstraint(fields=["number"], name="order_number_key"),
            models.CheckConstraint(
                condition=Q(state__in=ORDER_STATES), name="order_state_check"
            ),
            models.CheckConstraint(
                condition=Q(fulfillment_method__in=["delivery", "pickup"]),
                name="order_fulfillment_method_check",
            ),
            models.CheckConstraint(
                condition=Q(subtotal_cents__gte=0), name="order_subtotal_cents_check"
            ),
            models.CheckConstraint(
                condition=Q(shipping_cents__gte=0), name="order_shipping_cents_check"
            ),
            models.CheckConstraint(
                condition=Q(discount_cents__gte=0), name="order_discount_cents_check"
            ),
            models.CheckConstraint(
                condition=Q(total_cents__gte=0), name="order_total_cents_check"
            ),
            models.CheckConstraint(
                condition=Q(tax_included_cents__gte=0),
                name="order_tax_included_cents_check",
            ),
            models.CheckConstraint(
                condition=Q(
                    total_cents=F("subtotal_cents")
                    + F("shipping_cents")
                    - F("discount_cents")
                ),
                name="order_total_arithmetic",
            ),
            # Once past draft, the fulfillment target must be fully specified.
            models.CheckConstraint(
                condition=Q(state="draft")
                | Q(fulfillment_method="pickup", pickup_location__isnull=False)
                | Q(fulfillment_method="delivery", shipping_address__isnull=False),
                name="order_fulfillment_target_complete",
            ),
            models.CheckConstraint(
                condition=~Q(fulfillment_method="pickup") | Q(shipping_cents=0),
                name="order_pickup_has_no_shipping_fee",
            ),
            models.UniqueConstraint(
                fields=["cart_token", "idempotency_key"],
                condition=Q(idempotency_key__isnull=False),
                name="order_idempotency_uq",
            ),
        ]
        indexes = [
            models.Index(
                F("customer"), F("created_at").desc(), name="order_customer_idx"
            ),
            models.Index(F("state"), F("created_at").desc(), name="order_state_idx"),
            models.Index(fields=["email"], name="order_email_idx"),
            models.Index(
                fields=["payment_deadline_at"],
                condition=Q(state="pending_payment"),
                name="order_payment_deadline_idx",
            ),
        ]

    def __str__(self) -> str:
        return self.number


class OrderLine(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="lines", db_index=False
    )
    variant = models.ForeignKey(
        "catalog.Variant",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_index=False,
    )
    # Snapshots: an order line must remain readable after the catalog changes.
    sku = models.TextField()
    product_name = models.TextField()
    options_snapshot = models.JSONField(default=dict, db_default=json_default({}))
    image_key = models.TextField(default="", db_default="", blank=True)
    quantity = models.IntegerField()
    unit_price_cents = models.IntegerField()
    line_total_cents = models.IntegerField()
    # variant.cost_cents when the order was created; NULL if the variant had none (G33, ADR-0030).
    unit_cost_cents = models.IntegerField(null=True, blank=True)
    is_preorder = models.BooleanField(default=False, db_default=False)
    expected_release_date = models.DateField(null=True, blank=True)
    fulfilled_quantity = models.IntegerField(default=0, db_default=0)

    class Meta:
        db_table = "order_line"
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="order_line_quantity_check"
            ),
            models.CheckConstraint(
                condition=Q(unit_price_cents__gte=0),
                name="order_line_unit_price_cents_check",
            ),
            models.CheckConstraint(
                condition=Q(line_total_cents__gte=0),
                name="order_line_line_total_cents_check",
            ),
            models.CheckConstraint(
                condition=Q(unit_cost_cents__isnull=True) | Q(unit_cost_cents__gte=0),
                name="order_line_unit_cost_cents_check",
            ),
            models.CheckConstraint(
                condition=Q(fulfilled_quantity__gte=0),
                name="order_line_fulfilled_quantity_check",
            ),
            models.CheckConstraint(
                condition=Q(line_total_cents=F("unit_price_cents") * F("quantity")),
                name="order_line_total_arithmetic",
            ),
            models.CheckConstraint(
                condition=Q(fulfilled_quantity__lte=F("quantity")),
                name="order_line_fulfilled_le_qty",
            ),
        ]
        indexes = [models.Index(fields=["order"], name="order_line_order_idx")]


class OrderEvent(models.Model):
    """Every state change, append-only: the audit trail and the tool for out-of-order webhooks."""

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="events", db_index=False
    )
    from_state = models.TextField(null=True, blank=True)
    to_state = models.TextField(null=True, blank=True)
    event = models.TextField()  # 'checkout_started', 'payment_approved', ...
    # 'system', 'staff:<id>', 'customer', 'webhook'
    actor = models.TextField(default="system", db_default="system")
    payload = models.JSONField(default=dict, db_default=json_default({}))
    created_at = models.DateTimeField(default=timezone.now, db_default=NOW)

    class Meta:
        db_table = "order_event"
        indexes = [
            models.Index(fields=["order", "created_at"], name="order_event_order_idx")
        ]


class Shipment(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="shipments", db_index=False
    )
    carrier = models.TextField()
    tracking_number = models.TextField()
    tracking_url = models.TextField(default="", db_default="", blank=True)
    cost_cents = models.IntegerField(null=True, blank=True)
    shipped_at = models.DateTimeField(default=timezone.now, db_default=NOW)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "shipment"
        constraints = [
            models.CheckConstraint(
                condition=Q(cost_cents__isnull=True) | Q(cost_cents__gte=0),
                name="shipment_cost_cents_check",
            )
        ]
        # `shipment_order_idx` is a unique index (one shipment per order, OA-60), created by
        # `RunSQL` in migration 0002: Django's `UniqueConstraint` would make a constraint.
