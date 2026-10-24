"""Geography and shipping tables (§4.4, `spec/schema.sql` CUSTOMERS and SHIPPING)."""

from django.db import models
from django.db.models import F, Q

from apps.core.fields import CITextField, FixedCharField


class MxState(models.Model):
    code = FixedCharField(max_length=3, primary_key=True)  # ISO 3166-2:MX, e.g. 'CMX'
    name = models.TextField()

    class Meta:
        db_table = "mx_state"

    def __str__(self) -> str:
        return self.name


class MxPostalCode(models.Model):
    """CP → colonia/municipio/estado autofill, from the public SEPOMEX dataset."""

    pk = models.CompositePrimaryKey("postal_code", "neighborhood")
    postal_code = FixedCharField(max_length=5)
    neighborhood = models.TextField()
    municipality = models.TextField()
    state = models.ForeignKey(
        MxState, on_delete=models.DO_NOTHING, db_column="state_code", db_index=False
    )

    class Meta:
        db_table = "mx_postal_code"
        indexes = [models.Index(fields=["postal_code"], name="mx_postal_code_cp_idx")]


class ShippingZone(models.Model):
    code = CITextField(unique=True)  # 'local', 'centro', 'nacional'
    name = models.TextField()
    position = models.IntegerField(default=0, db_default=0)

    class Meta:
        db_table = "shipping_zone"

    def __str__(self) -> str:
        return self.name


class ShippingZoneState(models.Model):
    """Every Mexican state belongs to exactly one zone: the state is the primary key."""

    state = models.OneToOneField(
        MxState,
        primary_key=True,
        on_delete=models.DO_NOTHING,
        db_column="state_code",
        related_name="zone_link",
    )
    zone = models.ForeignKey(
        ShippingZone,
        on_delete=models.PROTECT,
        related_name="state_links",
        db_index=False,
    )

    class Meta:
        db_table = "shipping_zone_state"


class ShippingRate(models.Model):
    zone = models.ForeignKey(
        ShippingZone, on_delete=models.CASCADE, related_name="rates", db_index=False
    )
    name = models.TextField()
    min_subtotal_cents = models.IntegerField(default=0, db_default=0)
    max_subtotal_cents = models.IntegerField(null=True, blank=True)
    price_cents = models.IntegerField()
    eta_min_days = models.IntegerField(default=2, db_default=2)
    eta_max_days = models.IntegerField(default=7, db_default=7)
    is_active = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "shipping_rate"
        constraints = [
            models.CheckConstraint(
                condition=Q(min_subtotal_cents__gte=0),
                name="shipping_rate_min_subtotal_cents_check",
            ),
            models.CheckConstraint(
                condition=Q(max_subtotal_cents__isnull=True)
                | Q(max_subtotal_cents__gt=F("min_subtotal_cents")),
                name="shipping_rate_check",
            ),
            models.CheckConstraint(
                condition=Q(price_cents__gte=0), name="shipping_rate_price_cents_check"
            ),
        ]
        indexes = [
            models.Index(
                fields=["zone", "min_subtotal_cents"], name="shipping_rate_zone_idx"
            )
        ]

    def __str__(self) -> str:
        return self.name
