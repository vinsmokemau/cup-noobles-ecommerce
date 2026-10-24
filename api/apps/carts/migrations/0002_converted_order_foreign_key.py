import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """`converted_order_id` becomes a foreign key to `"order"` (spec/schema.sql, ORDERS).

    The column keeps its name and type; the named constraint is created by `RunSQL`.
    """

    dependencies = [
        ('carts', '0001_initial'),
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(model_name='cart', old_name='converted_order_id', new_name='converted_order'),
        migrations.AlterField(
            model_name='cart',
            name='converted_order',
            field=models.ForeignKey(blank=True, db_constraint=False, db_index=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to='orders.order'),
        ),
        migrations.RunSQL(
            sql="""
ALTER TABLE cart
  ADD CONSTRAINT cart_converted_order_fk
  FOREIGN KEY (converted_order_id) REFERENCES "order"(id) ON DELETE SET NULL;
""",
            reverse_sql="""
ALTER TABLE cart DROP CONSTRAINT cart_converted_order_fk;
""",
        ),
    ]
