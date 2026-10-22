# ADR-0004: Attribute-agnostic catalog

## Status

accepted (2026-10-21)

## Context

The catalog sells products with different attributes: trading cards, board games, apparel, figures and accessories (D14). A column per attribute would need a migration for every new attribute. The plan compared entity-attribute-value (EAV) tables, which make queries and validation hard, and one table per category, which multiplies models and code.

## Decision

Each `product_type` carries a JSON Schema that defines its attributes. Each `product` stores its values in a JSONB column, validated against its type's schema. Launch types and their schemas are placeholders until D14 is decided (ADR-0002).

## Consequences

- A new product type or attribute is data, not a migration.
- Facets and search read JSONB, so they depend on PostgreSQL (ADR-0003).
- Validation lives in the schema, not in the database, so the application must enforce it on every write.

## Source

Plan 2.4 and Appendix C; D14.
