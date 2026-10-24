from django.db import migrations


class Migration(migrations.Migration):
    """`variant_product_options_uq` is a unique index in spec/schema.sql, not a constraint.

    Django's `UniqueConstraint` always makes a constraint, so the index is created by `RunSQL`
    and the model no longer declares it (P2-V01). Rejection behaviour is unchanged (P2-V03).
    """

    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
ALTER TABLE variant DROP CONSTRAINT variant_product_options_uq;
CREATE UNIQUE INDEX variant_product_options_uq ON variant (product_id, options);
""",
            reverse_sql="""
DROP INDEX variant_product_options_uq;
ALTER TABLE variant ADD CONSTRAINT variant_product_options_uq UNIQUE (product_id, options);
""",
            state_operations=[
                migrations.RemoveConstraint(
                    model_name='variant', name='variant_product_options_uq'
                ),
            ],
        ),
    ]
