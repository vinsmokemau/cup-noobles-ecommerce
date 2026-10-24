import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """`order_id` becomes a foreign key to `"order"` (spec/schema.sql, ORDERS).

    The columns keep their names and types; only the model state changes. The named constraints
    are created by `RunSQL`, so the fields declare `db_constraint=False`.
    """

    dependencies = [
        ('inventory', '0001_initial'),
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.RemoveIndex(model_name='inventoryreservation', name='reservation_order_idx'),
        migrations.RemoveIndex(model_name='stockledger', name='stock_ledger_order_idx'),
        migrations.RenameField(model_name='inventoryreservation', old_name='order_id', new_name='order'),
        migrations.AlterField(
            model_name='inventoryreservation',
            name='order',
            field=models.ForeignKey(db_constraint=False, db_index=False, on_delete=django.db.models.deletion.CASCADE, to='orders.order'),
        ),
        migrations.RenameField(model_name='stockledger', old_name='order_id', new_name='order'),
        migrations.AlterField(
            model_name='stockledger',
            name='order',
            field=models.ForeignKey(blank=True, db_constraint=False, db_index=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to='orders.order'),
        ),
        migrations.AddIndex(model_name='inventoryreservation', index=models.Index(fields=['order'], name='reservation_order_idx')),
        migrations.AddIndex(model_name='stockledger', index=models.Index(fields=['order'], name='stock_ledger_order_idx')),
        migrations.RunSQL(
            sql="""
ALTER TABLE inventory_reservation
  ADD CONSTRAINT reservation_order_fk
  FOREIGN KEY (order_id) REFERENCES "order"(id) ON DELETE CASCADE;
ALTER TABLE stock_ledger
  ADD CONSTRAINT stock_ledger_order_fk
  FOREIGN KEY (order_id) REFERENCES "order"(id) ON DELETE SET NULL;
""",
            reverse_sql="""
ALTER TABLE stock_ledger DROP CONSTRAINT stock_ledger_order_fk;
ALTER TABLE inventory_reservation DROP CONSTRAINT reservation_order_fk;
""",
        ),
    ]
