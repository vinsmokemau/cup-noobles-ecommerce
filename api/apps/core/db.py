"""Database-side defaults shared by the models, so a raw INSERT gets the same values (§4.4)."""

from django.db.models import DateTimeField, Func, UUIDField

# `now()` rather than Django's `Now`, which renders STATEMENT_TIMESTAMP() on PostgreSQL.
NOW = Func(function="now", output_field=DateTimeField())
GEN_RANDOM_UUID = Func(function="gen_random_uuid", output_field=UUIDField())
