# ADR-0031: Foreign key delete rules are enforced by Django

## Status

accepted (2026-10-23)

## Context

`spec/schema.sql` states an `ON DELETE` rule for each foreign key (cascade, set null or restrict). Django 5.2 cannot put those rules in the database: it applies them in Python when a row is deleted through the ORM, and creates every unnamed foreign key as `NO ACTION` and deferrable. T2.1c found this while writing P2-V01.

Two alternatives were considered. Writing `RunSQL` for about 38 foreign keys would match the schema exactly, but Django does not track that SQL, so every later model change would need extra care. Waiting for Django 6.0, which adds native database-level delete rules, makes the fix cheap on upgrade.

## Decision

1. The delete rules are enforced by Django's ORM, which every app, service and admin delete uses.
2. Only the four foreign keys the schema names (`product_image_variant_fk`, `reservation_order_fk`, `stock_ledger_order_fk`, `cart_converted_order_fk`) are created by `RunSQL` with the exact rule.
3. P2-V01 compares the other foreign keys by columns and target table, not by delete action or deferrability.
4. The decision is revisited when the project moves to Django 6.0.

## Consequences

- Deletes through the app and the admin behave as the schema describes.
- A raw SQL delete that should cascade or null out dependents fails at commit instead, and one that should be blocked is still blocked. Both failures are safe.
- Moving to Django 6.0 needs a migration that sets the rules in the database, and a stricter P2-V01.

## Source

G40; OA-28 (2026-10-23); T2.1c.
