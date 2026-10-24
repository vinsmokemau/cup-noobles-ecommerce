"""Inventory tables (§4.4, `spec/schema.sql` INVENTORY).

The foreign keys from `stock_ledger.order_id` and `inventory_reservation.order_id` to `"order"`
are named constraints (`stock_ledger_order_fk`, `reservation_order_fk`) added by `RunSQL` in
inventory migration 0002, so the fields declare `db_constraint=False`.
Stock changes only through `apps/inventory/services.py` (CR-05).
"""

from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.core.db import NOW
from apps.core.fields import CITextField, FixedCharField


class Location(models.Model):
    class Kind(models.TextChoices):
        STORE = "store"
        WAREHOUSE = "warehouse"

    code = CITextField(unique=True)  # 'almacen' (D4); never shown as a store (CR-47)
    name = models.TextField()
    kind = models.TextField(choices=Kind.choices)
    is_pickup_point = models.BooleanField(default=False, db_default=False)
    is_fulfillment_source = models.BooleanField(default=True, db_default=True)
    address_line = models.TextField(default="", db_default="", blank=True)
    municipality = models.TextField(default="", db_default="", blank=True)
    state_code = FixedCharField(max_length=3, null=True, blank=True)
    postal_code = FixedCharField(max_length=5, null=True, blank=True)
    pickup_hours_note = models.TextField(default="", db_default="", blank=True)
    is_active = models.BooleanField(default=True, db_default=True)
    created_at = models.DateTimeField(default=timezone.now, db_default=NOW)

    class Meta:
        db_table = "location"
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=["store", "warehouse"]), name="location_kind_check"
            )
        ]

    def __str__(self) -> str:
        return self.name


class StockItem(models.Model):
    """One row per (variant, location). available = on_hand - reserved - safety_stock."""

    variant = models.ForeignKey(
        "catalog.Variant",
        on_delete=models.CASCADE,
        related_name="stock_items",
        db_index=False,
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="stock_items",
        db_index=False,
    )
    on_hand = models.IntegerField(default=0, db_default=0)
    reserved = models.IntegerField(default=0, db_default=0)
    safety_stock = models.IntegerField(default=0, db_default=0)
    # Optional picking location; changing it writes no ledger row (G34, ADR-0030).
    bin_location = models.TextField(default="", db_default="", blank=True)
    updated_at = models.DateTimeField(auto_now=True, db_default=NOW)

    class Meta:
        db_table = "stock_item"
        constraints = [
            models.UniqueConstraint(
                fields=["variant", "location"],
                name="stock_item_variant_id_location_id_key",
            ),
            models.CheckConstraint(
                condition=Q(on_hand__gte=0), name="stock_item_on_hand_check"
            ),
            models.CheckConstraint(
                condition=Q(reserved__gte=0), name="stock_item_reserved_check"
            ),
            models.CheckConstraint(
                condition=Q(safety_stock__gte=0), name="stock_item_safety_stock_check"
            ),
            # Hard invariant: you can never have more held than you physically have.
            models.CheckConstraint(
                condition=Q(reserved__lte=F("on_hand")),
                name="stock_reserved_le_on_hand",
            ),
        ]
        indexes = [models.Index(fields=["variant"], name="stock_item_variant_idx")]


class StockLedger(models.Model):
    """Append-only. Every change to `on_hand` writes a row, in the same transaction."""

    class Reason(models.TextChoices):
        RECEIPT = "receipt"
        SALE_ONLINE = "sale_online"
        SALE_IN_STORE = "sale_in_store"
        RETURN = "return"
        ADJUSTMENT = "adjustment"
        DAMAGE = "damage"
        COUNT_CORRECTION = "count_correction"
        TRANSFER_IN = "transfer_in"
        TRANSFER_OUT = "transfer_out"

    stock_item = models.ForeignKey(
        StockItem,
        on_delete=models.PROTECT,
        related_name="ledger_rows",
        db_index=False,
    )
    delta = models.IntegerField()
    balance_after = models.IntegerField()
    reason = models.TextField(choices=Reason.choices)
    order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_constraint=False,
        db_index=False,
    )
    actor_user_id = models.BigIntegerField(null=True, blank=True)
    note = models.TextField(default="", db_default="", blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_default=NOW)

    class Meta:
        db_table = "stock_ledger"
        constraints = [
            models.CheckConstraint(
                condition=~Q(delta=0), name="stock_ledger_delta_check"
            ),
            models.CheckConstraint(
                condition=Q(balance_after__gte=0),
                name="stock_ledger_balance_after_check",
            ),
            models.CheckConstraint(
                condition=Q(
                    reason__in=[
                        "receipt",
                        "sale_online",
                        "sale_in_store",
                        "return",
                        "adjustment",
                        "damage",
                        "count_correction",
                        "transfer_in",
                        "transfer_out",
                    ]
                ),
                name="stock_ledger_reason_check",
            ),
        ]
        indexes = [
            models.Index(
                F("stock_item"), F("created_at").desc(), name="stock_ledger_item_idx"
            ),
            models.Index(fields=["order"], name="stock_ledger_order_idx"),
        ]


class InventoryReservation(models.Model):
    """A hold on units between "checkout started" and "payment settled or window expired"."""

    class Kind(models.TextChoices):
        STOCK = "stock"
        PREORDER = "preorder"

    class State(models.TextChoices):
        HELD = "held"
        COMMITTED = "committed"
        RELEASED = "released"

    order = models.ForeignKey(
        "orders.Order", on_delete=models.CASCADE, db_constraint=False, db_index=False
    )
    variant = models.ForeignKey(
        "catalog.Variant", on_delete=models.PROTECT, db_index=False
    )
    # NULL for kind='preorder'.
    location = models.ForeignKey(
        Location, null=True, blank=True, on_delete=models.PROTECT, db_index=False
    )
    kind = models.TextField(choices=Kind.choices)
    quantity = models.IntegerField()
    state = models.TextField(
        choices=State.choices, default=State.HELD, db_default=State.HELD
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_default=NOW)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "inventory_reservation"
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=["stock", "preorder"]),
                name="inventory_reservation_kind_check",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="inventory_reservation_quantity_check"
            ),
            models.CheckConstraint(
                condition=Q(state__in=["held", "committed", "released"]),
                name="inventory_reservation_state_check",
            ),
            models.CheckConstraint(
                condition=~Q(kind="stock") | Q(location__isnull=False),
                name="reservation_stock_needs_location",
            ),
        ]
        indexes = [
            models.Index(
                fields=["expires_at"],
                condition=Q(state="held"),
                name="reservation_expiry_idx",
            ),
            models.Index(fields=["order"], name="reservation_order_idx"),
        ]


class InStoreSale(models.Model):
    """Counter sales recorded by staff in the admin. Unused in Release 1 (A11)."""

    location = models.ForeignKey(Location, on_delete=models.PROTECT, db_index=False)
    staff_user_id = models.BigIntegerField(null=True, blank=True)
    total_cents = models.IntegerField(default=0, db_default=0)
    note = models.TextField(default="", db_default="", blank=True)
    sold_at = models.DateTimeField(default=timezone.now, db_default=NOW)
    created_at = models.DateTimeField(default=timezone.now, db_default=NOW)

    class Meta:
        db_table = "in_store_sale"
        constraints = [
            models.CheckConstraint(
                condition=Q(total_cents__gte=0), name="in_store_sale_total_cents_check"
            )
        ]


class InStoreSaleLine(models.Model):
    sale = models.ForeignKey(
        InStoreSale, on_delete=models.CASCADE, related_name="lines", db_index=False
    )
    variant = models.ForeignKey(
        "catalog.Variant", on_delete=models.PROTECT, db_index=False
    )
    quantity = models.IntegerField()
    unit_price_cents = models.IntegerField()

    class Meta:
        db_table = "in_store_sale_line"
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="in_store_sale_line_quantity_check"
            ),
            models.CheckConstraint(
                condition=Q(unit_price_cents__gte=0),
                name="in_store_sale_line_unit_price_cents_check",
            ),
        ]
