"""Cart tables (§4.4, `spec/schema.sql` CART). The cart stores no prices (CR-03).

`converted_order` is a foreign key to `"order"`, the named constraint `cart_converted_order_fk`
added by `RunSQL` in carts migration 0002, so the field declares `db_constraint=False`.
"""

import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.db import GEN_RANDOM_UUID, NOW


class Cart(models.Model):
    token = models.UUIDField(
        default=uuid.uuid4, db_default=GEN_RANDOM_UUID, unique=True, editable=False
    )
    customer = models.ForeignKey(
        "accounts.Customer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_index=False,
    )
    fulfillment_method = models.TextField(null=True, blank=True)
    converted_order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_constraint=False,
        db_index=False,
    )
    created_at = models.DateTimeField(default=timezone.now, db_default=NOW)
    updated_at = models.DateTimeField(auto_now=True, db_default=NOW)

    class Meta:
        db_table = "cart"
        constraints = [
            models.CheckConstraint(
                condition=Q(fulfillment_method__in=["delivery", "pickup"]),
                name="cart_fulfillment_method_check",
            )
        ]
        indexes = [
            models.Index(fields=["customer"], name="cart_customer_idx"),
            models.Index(
                fields=["updated_at"],
                condition=Q(converted_order_id__isnull=True),
                name="cart_stale_idx",
            ),
        ]


class CartLine(models.Model):
    cart = models.ForeignKey(
        Cart, on_delete=models.CASCADE, related_name="lines", db_index=False
    )
    variant = models.ForeignKey(
        "catalog.Variant", on_delete=models.CASCADE, db_index=False
    )
    quantity = models.IntegerField()
    added_at = models.DateTimeField(default=timezone.now, db_default=NOW)

    class Meta:
        db_table = "cart_line"
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0, quantity__lte=99),
                name="cart_line_quantity_check",
            ),
            models.UniqueConstraint(
                fields=["cart", "variant"], name="cart_line_cart_id_variant_id_key"
            ),
        ]
