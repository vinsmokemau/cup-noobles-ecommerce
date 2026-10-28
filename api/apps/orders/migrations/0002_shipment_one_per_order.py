from django.db import migrations
from django.db.models import Count


def refuse_orders_with_many_shipments(apps, schema_editor):
    """No shipment is deleted or merged: the owner decides what to do with such an order."""
    Shipment = apps.get_model("orders", "Shipment")
    many = list(
        Shipment.objects.values("order__number")
        .annotate(n=Count("id"))
        .filter(n__gt=1)
        .order_by("order__number")
    )
    if many:
        listed = ", ".join(f"{row['order__number']} ({row['n']})" for row in many)
        raise RuntimeError(
            "Cannot make shipment.order_id unique: these orders have more than one shipment "
            f"(order number, shipments): {listed}. An order has at most one shipment "
            "(OA-60, ADR-0051). Resolve them by hand, then run the migration again."
        )


class Migration(migrations.Migration):
    """`shipment_order_idx` becomes a unique index: an order has at most one shipment
    (OA-60, ADR-0051, P10-V27).

    Django's `UniqueConstraint` always makes a constraint, and spec/schema.sql has an index,
    so `RunSQL` swaps it and the model no longer declares it (P2-V01).
    """

    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(refuse_orders_with_many_shipments, migrations.RunPython.noop),
        migrations.RunSQL(
            sql="""
DROP INDEX shipment_order_idx;
CREATE UNIQUE INDEX shipment_order_idx ON shipment (order_id);
""",
            reverse_sql="""
DROP INDEX shipment_order_idx;
CREATE INDEX shipment_order_idx ON shipment (order_id);
""",
            state_operations=[
                migrations.RemoveIndex(model_name="shipment", name="shipment_order_idx"),
            ],
        ),
    ]
