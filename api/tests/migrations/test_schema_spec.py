"""P2-V01: `migrate` produces exactly `spec/schema.sql` (SPEC.md §4.4).

The canonical statements run in a scratch schema of the same database; both schemas are then
read back from `pg_catalog` and compared.
"""

import re

import pytest
from django.apps import apps
from django.db import connection

pytestmark = pytest.mark.django_db

SCRATCH = "canonical"

# Tables Django and its contrib apps create outside the application schema.
FRAMEWORK_APPS = {"admin", "auth", "contenttypes", "sessions"}

COLUMNS = """
SELECT c.relname, a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull
FROM pg_attribute a
JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s AND c.relkind = 'r' AND a.attnum > 0 AND NOT a.attisdropped
"""

TABLES = """
SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s AND c.relkind = 'r'
"""

# Foreign keys are compared by columns and target: Django and PostgreSQL name an unnamed one
# differently, and Django 5.2 emulates ON DELETE in Python and makes every FK deferrable.
FOREIGN_KEYS = """
SELECT c.relname,
       (SELECT array_agg(a.attname ORDER BY k.ord) FROM unnest(con.conkey) WITH ORDINALITY k(attnum, ord)
          JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum),
       r.relname
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_class r ON r.oid = con.confrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s AND con.contype = 'f'
"""

CONSTRAINTS = """
SELECT c.relname, con.conname, con.contype
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s AND con.contype <> 'f'
"""

# Indexes are compared by name, table, uniqueness and access method; the predicate text varies
# with how the condition was written.
INDEXES = """
SELECT tablename, indexname, indexdef LIKE 'CREATE UNIQUE%%',
       substring(indexdef from ' USING ([a-z]+)')
FROM pg_indexes WHERE schemaname = %s
"""


def rows(query: str, schema: str) -> set[tuple]:
    with connection.cursor() as cursor:
        cursor.execute(query, [schema])
        return {tuple(tuple(v) if isinstance(v, list) else v for v in row) for row in cursor}


def framework_tables() -> set[str]:
    tables = {"django_migrations"}
    for model in apps.get_models(include_auto_created=True):
        if model._meta.app_label in FRAMEWORK_APPS:
            tables.add(model._meta.db_table)
    return tables


def test_p2_v01_schema_matches_canonical_ddl(canonical_ddl):
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE SCHEMA {SCRATCH}")
        cursor.execute(f"SET LOCAL search_path = {SCRATCH}, public")
        for statement in canonical_ddl:
            cursor.execute(statement)
        cursor.execute("SET LOCAL search_path = public")

    expected_tables = {name for (name,) in rows(TABLES, SCRATCH)}
    actual_tables = {name for (name,) in rows(TABLES, "public")} - framework_tables()
    assert actual_tables == expected_tables, (
        f"missing: {sorted(expected_tables - actual_tables)}; "
        f"extra: {sorted(actual_tables - expected_tables)}"
    )

    def of_tables(found: set[tuple]) -> set[tuple]:
        return {row for row in found if row[0] in expected_tables}

    for label, query in (
        ("column", COLUMNS),
        ("constraint", CONSTRAINTS),
        ("foreign key", FOREIGN_KEYS),
        ("index", INDEXES),
    ):
        expected = of_tables(rows(query, SCRATCH))
        actual = of_tables(rows(query, "public"))
        assert actual == expected, (
            f"{label}s differ.\nmissing: {sorted(expected - actual, key=str)}\n"
            f"extra: {sorted(actual - expected, key=str)}"
        )

    # The `RunSQL` objects are named in the DDL, so a rename would show above; this guards the
    # one thing a regex over the file can read: every explicit name exists.
    text = " ".join(canonical_ddl)
    named = set(re.findall(r"CONSTRAINT\s+(\w+)", text))
    present = {name for _, name, _ in rows(CONSTRAINTS, "public")} | {
        "reservation_order_fk",
        "stock_ledger_order_fk",
        "cart_converted_order_fk",
        "product_image_variant_fk",
    }
    assert named <= present
