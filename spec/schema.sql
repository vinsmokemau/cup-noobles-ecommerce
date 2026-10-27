-- =====================================================================
-- Cup Noobles — canonical schema (PostgreSQL 16+)
-- Normative part of SPEC.md (§4.4). Django migrations must produce exactly
-- this schema (P2-V01). It changes only under the amendment rule (SPEC.md §8).
-- Money: integer centavos MXN, IVA-inclusive (assumption A2).
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS citext;     -- case-insensitive slugs/emails
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- fuzzy product search

-- ---------------------------------------------------------------------
-- CATALOG
-- ---------------------------------------------------------------------

-- A product_type defines what attributes its products may carry and which
-- axes their variants vary along. Adding a new pop-culture category is an
-- INSERT here plus rows in product — never a migration. This is the
-- attribute-agnostic requirement, discharged.
CREATE TABLE product_type (
  id                bigserial PRIMARY KEY,
  code              citext      NOT NULL UNIQUE,   -- 'tcg_sealed','board_game','figure','accessory' (D14)
  name              text        NOT NULL,
  -- JSON Schema (draft 2020-12) validated in the application on save.
  attribute_schema  jsonb       NOT NULL DEFAULT '{"type":"object","properties":{},"additionalProperties":false}'::jsonb,
  -- Default variant axes for products of this type, e.g. ["talla","color"].
  variant_axes      jsonb       NOT NULL DEFAULT '[]'::jsonb,
  -- Attribute keys surfaced as storefront filters, ordered.
  filterable_keys   jsonb       NOT NULL DEFAULT '[]'::jsonb,
  position          integer     NOT NULL DEFAULT 0,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT product_type_schema_is_object CHECK (jsonb_typeof(attribute_schema) = 'object'),
  CONSTRAINT product_type_axes_is_array    CHECK (jsonb_typeof(variant_axes)     = 'array')
);

CREATE TABLE category (
  id          bigserial PRIMARY KEY,
  parent_id   bigint      NULL REFERENCES category(id) ON DELETE RESTRICT,
  slug        citext      NOT NULL UNIQUE,
  name        text        NOT NULL,
  description text        NOT NULL DEFAULT '',
  position    integer     NOT NULL DEFAULT 0,
  is_active   boolean     NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT category_not_self_parent CHECK (parent_id IS DISTINCT FROM id)
);
CREATE INDEX category_parent_idx ON category(parent_id);

-- Franchise = the IP (Pokémon, One Piece, Zelda). Brand = the maker
-- (Good Smile Company, Bandai, Konami). Both optional on a product.
CREATE TABLE franchise (
  id bigserial PRIMARY KEY,
  slug citext NOT NULL UNIQUE,
  name text NOT NULL,
  is_active boolean NOT NULL DEFAULT true
);

CREATE TABLE brand (
  id bigserial PRIMARY KEY,
  slug citext NOT NULL UNIQUE,
  name text NOT NULL,
  is_active boolean NOT NULL DEFAULT true
);

CREATE TABLE product (
  id               bigserial PRIMARY KEY,
  public_id        uuid        NOT NULL DEFAULT gen_random_uuid() UNIQUE,
  product_type_id  bigint      NOT NULL REFERENCES product_type(id) ON DELETE RESTRICT,
  brand_id         bigint      NULL REFERENCES brand(id)     ON DELETE SET NULL,
  franchise_id     bigint      NULL REFERENCES franchise(id) ON DELETE SET NULL,
  slug             citext      NOT NULL UNIQUE,
  name             text        NOT NULL,
  subtitle         text        NOT NULL DEFAULT '',
  description_md   text        NOT NULL DEFAULT '',
  status           text        NOT NULL DEFAULT 'draft'
                     CHECK (status IN ('draft','active','archived')),
  -- Per-category attributes. Shape is governed by product_type.attribute_schema.
  -- e.g. TCG box:  {"juego":"Pokémon TCG","set":"Prismatic Evolutions",
  --                 "idioma":"inglés","sobres_por_caja":36}
  --      figure:   {"linea":"Nendoroid","numero":1234,"escala":"non-scale",
  --                 "altura_mm":100,"fabricante":"Good Smile Company"}
  --      apparel:  {"material":"algodón 100%","corte":"unisex"}
  attributes       jsonb       NOT NULL DEFAULT '{}'::jsonb,
  -- Overrides product_type.variant_axes when a product is unusual.
  variant_axes     jsonb       NULL,
  -- Home-page featured products, shown in featured_position order (G28, ADR-0030).
  -- Related products need no column: same franchise or a shared category.
  is_featured      boolean     NOT NULL DEFAULT false,
  featured_position integer    NOT NULL DEFAULT 0 CHECK (featured_position >= 0),
  search_tsv       tsvector GENERATED ALWAYS AS (
                     setweight(to_tsvector('spanish', coalesce(name,'')), 'A') ||
                     setweight(to_tsvector('spanish', coalesce(subtitle,'')), 'B') ||
                     setweight(to_tsvector('spanish', coalesce(description_md,'')), 'C')
                   ) STORED,
  published_at     timestamptz NULL,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT product_attributes_is_object CHECK (jsonb_typeof(attributes) = 'object'),
  CONSTRAINT product_active_needs_publish CHECK (status <> 'active' OR published_at IS NOT NULL)
);
CREATE INDEX product_attributes_gin ON product USING gin (attributes jsonb_path_ops);
CREATE INDEX product_search_gin     ON product USING gin (search_tsv);
CREATE INDEX product_name_trgm      ON product USING gin (name gin_trgm_ops);
CREATE INDEX product_active_idx     ON product (status, published_at DESC) WHERE status = 'active';
CREATE INDEX product_type_idx       ON product (product_type_id);
CREATE INDEX product_franchise_idx  ON product (franchise_id);
CREATE INDEX product_featured_idx   ON product (featured_position) WHERE status = 'active' AND is_featured;

CREATE TABLE product_category (
  product_id  bigint NOT NULL REFERENCES product(id)  ON DELETE CASCADE,
  category_id bigint NOT NULL REFERENCES category(id) ON DELETE CASCADE,
  PRIMARY KEY (product_id, category_id)
);
CREATE INDEX product_category_cat_idx ON product_category(category_id);

CREATE TABLE product_image (
  id          bigserial PRIMARY KEY,
  product_id  bigint  NOT NULL REFERENCES product(id) ON DELETE CASCADE,
  variant_id  bigint  NULL,   -- FK added after variant exists
  storage_key text    NOT NULL,     -- object-storage key, not a URL
  alt         text    NOT NULL DEFAULT '',
  width       integer NULL,
  height      integer NULL,
  position    integer NOT NULL DEFAULT 0,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX product_image_product_idx ON product_image(product_id, position);

-- A variant is the sellable unit. A product with no meaningful variation
-- still has exactly one variant with options = '{}'. This keeps every
-- downstream table (stock, cart, order) uniform.
CREATE TABLE variant (
  id                 bigserial PRIMARY KEY,
  public_id          uuid        NOT NULL DEFAULT gen_random_uuid() UNIQUE,
  product_id         bigint      NOT NULL REFERENCES product(id) ON DELETE CASCADE,
  sku                citext      NOT NULL UNIQUE,
  barcode            text        NULL,
  -- Values along the product's variant_axes: {"talla":"L","color":"negro"}
  -- jsonb normalises key order, so equality and the unique index are stable.
  options            jsonb       NOT NULL DEFAULT '{}'::jsonb,
  price_cents        integer     NOT NULL CHECK (price_cents >= 0),
  compare_at_cents   integer     NULL     CHECK (compare_at_cents IS NULL OR compare_at_cents >= 0),
  cost_cents         integer     NULL     CHECK (cost_cents IS NULL OR cost_cents >= 0),
  weight_grams       integer     NOT NULL DEFAULT 0 CHECK (weight_grams >= 0),
  requires_shipping  boolean     NOT NULL DEFAULT true,
  is_active          boolean     NOT NULL DEFAULT true,
  position           integer     NOT NULL DEFAULT 0,
  -- Per-customer purchase limit in units; NULL means no limit (G31, ADR-0030).
  purchase_limit     integer     NULL     CHECK (purchase_limit IS NULL OR purchase_limit > 0),
  -- Pre-order support. Pre-order stock is NOT drawn from stock_item.
  is_preorder            boolean NOT NULL DEFAULT false,
  preorder_limit         integer NULL CHECK (preorder_limit IS NULL OR preorder_limit >= 0),
  preorder_committed     integer NOT NULL DEFAULT 0 CHECK (preorder_committed >= 0),
  expected_release_date  date    NULL,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT variant_options_is_object CHECK (jsonb_typeof(options) = 'object'),
  CONSTRAINT variant_preorder_needs_date
    CHECK (NOT is_preorder OR expected_release_date IS NOT NULL),
  CONSTRAINT variant_preorder_within_limit
    CHECK (preorder_limit IS NULL OR preorder_committed <= preorder_limit)
);
CREATE UNIQUE INDEX variant_product_options_uq ON variant (product_id, options);
CREATE INDEX variant_product_idx  ON variant (product_id);
CREATE INDEX variant_options_gin  ON variant USING gin (options jsonb_path_ops);

ALTER TABLE product_image
  ADD CONSTRAINT product_image_variant_fk
  FOREIGN KEY (variant_id) REFERENCES variant(id) ON DELETE SET NULL;

-- ---------------------------------------------------------------------
-- INVENTORY  (the system of record for physical stock)
-- ---------------------------------------------------------------------

CREATE TABLE location (
  id                    bigserial PRIMARY KEY,
  code                  citext NOT NULL UNIQUE,   -- 'almacen' (D4); never shown as a store (CR-47)
  name                  text   NOT NULL,
  kind                  text   NOT NULL CHECK (kind IN ('store','warehouse')),
  is_pickup_point       boolean NOT NULL DEFAULT false,
  is_fulfillment_source boolean NOT NULL DEFAULT true,
  address_line          text   NOT NULL DEFAULT '',
  municipality          text   NOT NULL DEFAULT '',
  state_code            char(3) NULL,
  postal_code           char(5) NULL,
  pickup_hours_note     text   NOT NULL DEFAULT '',
  is_active             boolean NOT NULL DEFAULT true,
  created_at            timestamptz NOT NULL DEFAULT now()
);

-- One row per (variant, location). available = on_hand - reserved - safety_stock.
CREATE TABLE stock_item (
  id           bigserial PRIMARY KEY,
  variant_id   bigint  NOT NULL REFERENCES variant(id)  ON DELETE CASCADE,
  location_id  bigint  NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
  on_hand      integer NOT NULL DEFAULT 0 CHECK (on_hand  >= 0),
  reserved     integer NOT NULL DEFAULT 0 CHECK (reserved >= 0),
  safety_stock integer NOT NULL DEFAULT 0 CHECK (safety_stock >= 0),
  -- Optional picking location ("ubicación"); changing it writes no ledger row (G34, ADR-0030).
  bin_location text    NOT NULL DEFAULT '',
  updated_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (variant_id, location_id),
  -- Hard invariant: you can never have more held than you physically have.
  CONSTRAINT stock_reserved_le_on_hand CHECK (reserved <= on_hand)
);
CREATE INDEX stock_item_variant_idx ON stock_item(variant_id);

-- Append-only. Every change to on_hand writes a row here, in the same
-- transaction. This is how you answer "where did that unit go".
-- Reservations do NOT appear here; they only move stock_item.reserved.
CREATE TABLE stock_ledger (
  id            bigserial PRIMARY KEY,
  stock_item_id bigint  NOT NULL REFERENCES stock_item(id) ON DELETE RESTRICT,
  delta         integer NOT NULL CHECK (delta <> 0),
  balance_after integer NOT NULL CHECK (balance_after >= 0),
  reason        text    NOT NULL CHECK (reason IN (
                  'receipt','sale_online','sale_in_store','return',
                  'adjustment','damage','count_correction',
                  'transfer_in','transfer_out')),
  order_id      bigint  NULL,   -- FK added after "order" exists
  actor_user_id bigint  NULL,
  note          text    NOT NULL DEFAULT '',
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX stock_ledger_item_idx  ON stock_ledger(stock_item_id, created_at DESC);
CREATE INDEX stock_ledger_order_idx ON stock_ledger(order_id);

-- A hold on units between "customer started checkout" and
-- "payment settled or window expired".
CREATE TABLE inventory_reservation (
  id          bigserial PRIMARY KEY,
  order_id    bigint  NOT NULL,   -- FK added after "order" exists
  variant_id  bigint  NOT NULL REFERENCES variant(id) ON DELETE RESTRICT,
  location_id bigint  NULL REFERENCES location(id) ON DELETE RESTRICT, -- NULL for kind='preorder'
  kind        text    NOT NULL CHECK (kind IN ('stock','preorder')),
  quantity    integer NOT NULL CHECK (quantity > 0),
  state       text    NOT NULL DEFAULT 'held'
                CHECK (state IN ('held','committed','released')),
  expires_at  timestamptz NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  settled_at  timestamptz NULL,
  CONSTRAINT reservation_stock_needs_location
    CHECK (kind <> 'stock' OR location_id IS NOT NULL)
);
CREATE INDEX reservation_expiry_idx ON inventory_reservation (expires_at)
  WHERE state = 'held';
CREATE INDEX reservation_order_idx  ON inventory_reservation (order_id);

-- Counter sales, recorded by staff in the admin (no POS). Unused in Release 1
-- (A11); kept so a later release needs no migration.
CREATE TABLE in_store_sale (
  id            bigserial PRIMARY KEY,
  location_id   bigint  NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
  staff_user_id bigint  NULL,
  total_cents   integer NOT NULL DEFAULT 0 CHECK (total_cents >= 0),
  note          text    NOT NULL DEFAULT '',
  sold_at       timestamptz NOT NULL DEFAULT now(),
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE in_store_sale_line (
  id               bigserial PRIMARY KEY,
  sale_id          bigint  NOT NULL REFERENCES in_store_sale(id) ON DELETE CASCADE,
  variant_id       bigint  NOT NULL REFERENCES variant(id) ON DELETE RESTRICT,
  quantity         integer NOT NULL CHECK (quantity > 0),
  unit_price_cents integer NOT NULL CHECK (unit_price_cents >= 0)
);

-- ---------------------------------------------------------------------
-- CUSTOMERS
-- ---------------------------------------------------------------------

-- This is Django's AUTH_USER_MODEL. Set it before the first migration.
CREATE TABLE customer (
  id                bigserial PRIMARY KEY,
  public_id         uuid   NOT NULL DEFAULT gen_random_uuid() UNIQUE,
  email             citext NOT NULL UNIQUE,
  password          text   NOT NULL,          -- argon2 hash, managed by Django
  full_name         text   NOT NULL DEFAULT '',
  phone             text   NOT NULL DEFAULT '',
  email_verified_at timestamptz NULL,
  accepts_marketing boolean NOT NULL DEFAULT false,
  is_active         boolean NOT NULL DEFAULT true,
  is_staff          boolean NOT NULL DEFAULT false,
  is_superuser      boolean NOT NULL DEFAULT false,
  last_login        timestamptz NULL,
  date_joined       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE mx_state (
  code char(3) PRIMARY KEY,     -- ISO 3166-2:MX subdivision, e.g. 'AGU','CMX','JAL'
  name text NOT NULL
);

-- Optional convenience table for CP → colonia/municipio/estado autofill.
-- Populated from the public SEPOMEX dataset. Not required for correctness.
CREATE TABLE mx_postal_code (
  postal_code  char(5) NOT NULL,
  neighborhood text    NOT NULL,
  municipality text    NOT NULL,
  state_code   char(3) NOT NULL REFERENCES mx_state(code),
  PRIMARY KEY (postal_code, neighborhood)
);
CREATE INDEX mx_postal_code_cp_idx ON mx_postal_code(postal_code);

CREATE TABLE address (
  id              bigserial PRIMARY KEY,
  customer_id     bigint  NOT NULL REFERENCES customer(id) ON DELETE CASCADE,
  label           text    NOT NULL DEFAULT '',        -- 'Casa', 'Oficina'
  recipient_name  text    NOT NULL,
  phone           text    NOT NULL,
  street          text    NOT NULL,                   -- calle
  ext_number      text    NOT NULL,                   -- número exterior
  int_number      text    NOT NULL DEFAULT '',        -- número interior
  neighborhood    text    NOT NULL,                   -- colonia
  municipality    text    NOT NULL,                   -- municipio / alcaldía
  state_code      char(3) NOT NULL REFERENCES mx_state(code),
  postal_code     char(5) NOT NULL CHECK (postal_code ~ '^[0-9]{5}$'),
  delivery_notes  text    NOT NULL DEFAULT '',        -- referencias
  is_default      boolean NOT NULL DEFAULT false,
  deleted_at      timestamptz NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX address_customer_idx ON address(customer_id) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX address_single_default_uq ON address(customer_id)
  WHERE is_default AND deleted_at IS NULL;

-- ---------------------------------------------------------------------
-- SHIPPING
-- ---------------------------------------------------------------------

CREATE TABLE shipping_zone (
  id        bigserial PRIMARY KEY,
  code      citext NOT NULL UNIQUE,   -- 'local','centro','nacional'
  name      text   NOT NULL,
  position  integer NOT NULL DEFAULT 0
);

-- Every Mexican state belongs to exactly one zone: state_code is the PK.
CREATE TABLE shipping_zone_state (
  state_code char(3) PRIMARY KEY REFERENCES mx_state(code),
  zone_id    bigint  NOT NULL REFERENCES shipping_zone(id) ON DELETE RESTRICT
);

CREATE TABLE shipping_rate (
  id                  bigserial PRIMARY KEY,
  zone_id             bigint  NOT NULL REFERENCES shipping_zone(id) ON DELETE CASCADE,
  name                text    NOT NULL,      -- 'Envío estándar'
  min_subtotal_cents  integer NOT NULL DEFAULT 0 CHECK (min_subtotal_cents >= 0),
  max_subtotal_cents  integer NULL CHECK (max_subtotal_cents IS NULL OR max_subtotal_cents > min_subtotal_cents),
  price_cents         integer NOT NULL CHECK (price_cents >= 0),
  eta_min_days        integer NOT NULL DEFAULT 2,
  eta_max_days        integer NOT NULL DEFAULT 7,
  is_active           boolean NOT NULL DEFAULT true
);
CREATE INDEX shipping_rate_zone_idx ON shipping_rate(zone_id, min_subtotal_cents);

-- ---------------------------------------------------------------------
-- CART
-- ---------------------------------------------------------------------

CREATE TABLE cart (
  id                 bigserial PRIMARY KEY,
  token              uuid   NOT NULL DEFAULT gen_random_uuid() UNIQUE,
  customer_id        bigint NULL REFERENCES customer(id) ON DELETE SET NULL,
  fulfillment_method text   NULL CHECK (fulfillment_method IN ('delivery','pickup')),
  converted_order_id bigint NULL,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX cart_customer_idx ON cart(customer_id);
CREATE INDEX cart_stale_idx    ON cart(updated_at) WHERE converted_order_id IS NULL;

CREATE TABLE cart_line (
  id          bigserial PRIMARY KEY,
  cart_id     bigint  NOT NULL REFERENCES cart(id)    ON DELETE CASCADE,
  variant_id  bigint  NOT NULL REFERENCES variant(id) ON DELETE CASCADE,
  quantity    integer NOT NULL CHECK (quantity > 0 AND quantity <= 99),
  added_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (cart_id, variant_id)
);

-- ---------------------------------------------------------------------
-- ORDERS
-- ---------------------------------------------------------------------

CREATE TABLE "order" (
  id                  bigserial PRIMARY KEY,
  public_id           uuid   NOT NULL DEFAULT gen_random_uuid() UNIQUE,
  -- 'CN-{YYYY}-{seq:06d}'. The year is taken in America/Mexico_City, from one Postgres
  -- sequence per year that the service creates on first use (G5, ADR-0030). The
  -- sequences are not part of this DDL.
  number              text   NOT NULL UNIQUE,     -- 'CN-2026-000123'
  customer_id         bigint NULL REFERENCES customer(id) ON DELETE SET NULL,
  email               citext NOT NULL,            -- always set; guest checkout supported
  phone               text   NOT NULL DEFAULT '',
  state               text   NOT NULL CHECK (state IN (
                        'draft','pending_payment','paid','awaiting_stock',
                        'preparing','ready_for_pickup','shipped','delivered',
                        'picked_up','completed','cancelled','expired',
                        'refunded','partially_refunded')),
  fulfillment_method  text   NOT NULL CHECK (fulfillment_method IN ('delivery','pickup')),
  pickup_location_id  bigint NULL REFERENCES location(id) ON DELETE RESTRICT,
  -- Frozen snapshot. Never a FK to address: the customer may edit or delete it.
  shipping_address    jsonb  NULL,
  shipping_rate_name  text   NOT NULL DEFAULT '',
  subtotal_cents      integer NOT NULL CHECK (subtotal_cents >= 0),
  shipping_cents      integer NOT NULL DEFAULT 0 CHECK (shipping_cents >= 0),
  discount_cents      integer NOT NULL DEFAULT 0 CHECK (discount_cents >= 0),
  total_cents         integer NOT NULL CHECK (total_cents >= 0),
  -- IVA contained within total_cents (prices are IVA-inclusive, A2).
  tax_included_cents  integer NOT NULL DEFAULT 0 CHECK (tax_included_cents >= 0),
  currency            char(3) NOT NULL DEFAULT 'MXN',
  has_preorder_items  boolean NOT NULL DEFAULT false,
  earliest_release_date date  NULL,
  payment_deadline_at timestamptz NULL,
  pickup_deadline_at  timestamptz NULL,
  customer_note       text NOT NULL DEFAULT '',
  internal_note       text NOT NULL DEFAULT '',
  cancel_reason       text NOT NULL DEFAULT '',
  -- Checkout idempotency (G3, ADR-0030). The key is scoped to the cart token; the
  -- fingerprint is the SHA-256 hex digest of the canonical request body.
  cart_token               uuid NULL,
  idempotency_key          text NULL,
  idempotency_fingerprint  text NULL,
  placed_at           timestamptz NULL,
  paid_at             timestamptz NULL,
  shipped_at          timestamptz NULL,
  completed_at        timestamptz NULL,
  cancelled_at        timestamptz NULL,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT order_total_arithmetic
    CHECK (total_cents = subtotal_cents + shipping_cents - discount_cents),
  -- Once past draft, the fulfillment target must be fully specified.
  CONSTRAINT order_fulfillment_target_complete CHECK (
    state = 'draft'
    OR (fulfillment_method = 'pickup'   AND pickup_location_id IS NOT NULL)
    OR (fulfillment_method = 'delivery' AND shipping_address   IS NOT NULL)
  ),
  CONSTRAINT order_pickup_has_no_shipping_fee
    CHECK (fulfillment_method <> 'pickup' OR shipping_cents = 0),
  CONSTRAINT order_idempotency_complete CHECK (
    (idempotency_key IS NULL) = (idempotency_fingerprint IS NULL)
    AND (idempotency_key IS NULL OR cart_token IS NOT NULL)
  )
);
CREATE INDEX order_customer_idx ON "order"(customer_id, created_at DESC);
CREATE INDEX order_state_idx    ON "order"(state, created_at DESC);
CREATE INDEX order_email_idx    ON "order"(email);
CREATE UNIQUE INDEX order_idempotency_uq ON "order"(cart_token, idempotency_key)
  WHERE idempotency_key IS NOT NULL;
CREATE INDEX order_payment_deadline_idx ON "order"(payment_deadline_at)
  WHERE state = 'pending_payment';

CREATE TABLE order_line (
  id                    bigserial PRIMARY KEY,
  order_id              bigint  NOT NULL REFERENCES "order"(id) ON DELETE CASCADE,
  variant_id            bigint  NULL REFERENCES variant(id) ON DELETE SET NULL,
  -- Snapshots: an order line must remain readable after the catalog changes.
  sku                   text    NOT NULL,
  product_name          text    NOT NULL,
  options_snapshot      jsonb   NOT NULL DEFAULT '{}'::jsonb,
  image_key             text    NOT NULL DEFAULT '',
  quantity              integer NOT NULL CHECK (quantity > 0),
  unit_price_cents      integer NOT NULL CHECK (unit_price_cents >= 0),
  line_total_cents      integer NOT NULL CHECK (line_total_cents >= 0),
  -- variant.cost_cents when the order was created; NULL if the variant had none (G33, ADR-0030).
  unit_cost_cents       integer NULL CHECK (unit_cost_cents IS NULL OR unit_cost_cents >= 0),
  is_preorder           boolean NOT NULL DEFAULT false,
  expected_release_date date    NULL,
  fulfilled_quantity    integer NOT NULL DEFAULT 0 CHECK (fulfilled_quantity >= 0),
  CONSTRAINT order_line_total_arithmetic
    CHECK (line_total_cents = unit_price_cents * quantity),
  CONSTRAINT order_line_fulfilled_le_qty
    CHECK (fulfilled_quantity <= quantity)
);
CREATE INDEX order_line_order_idx ON order_line(order_id);

-- Every state change, append-only. This is the audit trail and the
-- debugging tool when a webhook arrives out of order.
CREATE TABLE order_event (
  id         bigserial PRIMARY KEY,
  order_id   bigint NOT NULL REFERENCES "order"(id) ON DELETE CASCADE,
  from_state text   NULL,
  to_state   text   NULL,
  event      text   NOT NULL,     -- 'checkout_started','payment_approved',...
  actor      text   NOT NULL DEFAULT 'system',  -- 'system','staff:<id>','customer','webhook'
  payload    jsonb  NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX order_event_order_idx ON order_event(order_id, created_at);

ALTER TABLE inventory_reservation
  ADD CONSTRAINT reservation_order_fk
  FOREIGN KEY (order_id) REFERENCES "order"(id) ON DELETE CASCADE;

ALTER TABLE stock_ledger
  ADD CONSTRAINT stock_ledger_order_fk
  FOREIGN KEY (order_id) REFERENCES "order"(id) ON DELETE SET NULL;

ALTER TABLE cart
  ADD CONSTRAINT cart_converted_order_fk
  FOREIGN KEY (converted_order_id) REFERENCES "order"(id) ON DELETE SET NULL;

-- ---------------------------------------------------------------------
-- PAYMENTS
-- ---------------------------------------------------------------------

CREATE TABLE payment (
  id                     bigserial PRIMARY KEY,
  order_id               bigint  NOT NULL REFERENCES "order"(id) ON DELETE RESTRICT,
  provider               text    NOT NULL DEFAULT 'mercadopago',
  provider_preference_id text    NULL,
  provider_payment_id    text    NULL,
  method                 text    NULL,   -- 'credit_card','debit_card','oxxo','spei','wallet','account_money'
  status                 text    NOT NULL CHECK (status IN (
                           'initiated','pending','authorized','approved',
                           'rejected','cancelled','refunded','partially_refunded',
                           'charged_back')),
  amount_cents           integer NOT NULL CHECK (amount_cents >= 0),
  refunded_cents         integer NOT NULL DEFAULT 0 CHECK (refunded_cents >= 0),
  installments           integer NULL CHECK (installments IS NULL OR installments > 0),
  voucher_url            text    NULL,   -- OXXO ficha
  voucher_expires_at     timestamptz NULL,
  raw                    jsonb   NOT NULL DEFAULT '{}'::jsonb,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT payment_refund_le_amount CHECK (refunded_cents <= amount_cents)
);
CREATE UNIQUE INDEX payment_provider_payment_uq
  ON payment(provider, provider_payment_id) WHERE provider_payment_id IS NOT NULL;
CREATE INDEX payment_order_idx ON payment(order_id);

-- Idempotency + forensics for provider callbacks. Insert first, process after.
CREATE TABLE webhook_event (
  id           bigserial PRIMARY KEY,
  provider     text    NOT NULL,
  topic        text    NOT NULL,      -- 'payment','merchant_order'
  external_id  text    NOT NULL,      -- provider notification (delivery) id, NOT the payment id (9.A rule 4)
  signature_ok boolean NOT NULL,
  payload      jsonb   NOT NULL,
  headers      jsonb   NOT NULL DEFAULT '{}'::jsonb,
  received_at  timestamptz NOT NULL DEFAULT now(),
  processed_at timestamptz NULL,
  attempts     integer NOT NULL DEFAULT 0,
  error        text    NOT NULL DEFAULT '',
  UNIQUE (provider, topic, external_id)
);
CREATE INDEX webhook_unprocessed_idx ON webhook_event(received_at)
  WHERE processed_at IS NULL;

-- ---------------------------------------------------------------------
-- INVOICING  (CFDI issued by hand in Release 1 — A8, ADR-0019)
-- ---------------------------------------------------------------------

-- At most one CFDI request per order. The customer's fiscal data is captured
-- at checkout; staff issue the CFDI outside the store and record it here.
-- The field list and the catalog codes are confirmed by the accountant (D16).
CREATE TABLE invoice_request (
  id                  bigserial PRIMARY KEY,
  order_id            bigint  NOT NULL UNIQUE REFERENCES "order"(id) ON DELETE RESTRICT,
  rfc                 citext  NOT NULL,                -- format checked by the application
  legal_name          text    NOT NULL,                -- nombre o razón social
  fiscal_postal_code  char(5) NOT NULL CHECK (fiscal_postal_code ~ '^[0-9]{5}$'),
  tax_regime          text    NOT NULL,                -- régimen fiscal, SAT catalog code
  cfdi_use            text    NOT NULL,                -- uso de CFDI, SAT catalog code
  status              text    NOT NULL DEFAULT 'requested'
                        CHECK (status IN ('requested','issued','cancelled')),
  folio               text    NOT NULL DEFAULT '',
  cfdi_uuid           uuid    NULL UNIQUE,             -- folio fiscal
  issued_at           timestamptz NULL,
  issued_by_user_id   bigint  NULL,
  cancelled_at        timestamptz NULL,
  -- Set when an order with an issued CFDI is refunded; the accountant decides
  -- the fiscal treatment (A12, D16).
  needs_review        boolean NOT NULL DEFAULT false,
  review_note         text    NOT NULL DEFAULT '',
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT invoice_issued_complete CHECK (
    status <> 'issued' OR (cfdi_uuid IS NOT NULL AND issued_at IS NOT NULL)),
  CONSTRAINT invoice_cancelled_dated CHECK (
    status <> 'cancelled' OR cancelled_at IS NOT NULL)
);
CREATE INDEX invoice_request_queue_idx ON invoice_request(created_at)
  WHERE status = 'requested' OR needs_review;

-- The PDF and XML the owner uploads. Kept in the database, not in public media
-- storage, because they hold the customer's fiscal data. An issued request has
-- one of each (enforced by the service, P10-V23).
CREATE TABLE invoice_document (
  id                 bigserial PRIMARY KEY,
  invoice_request_id bigint   NOT NULL REFERENCES invoice_request(id) ON DELETE CASCADE,
  kind               text     NOT NULL CHECK (kind IN ('pdf','xml')),
  filename           text     NOT NULL,
  content            bytea    NOT NULL,
  sha256             char(64) NOT NULL,
  size_bytes         integer  NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 5242880),
  uploaded_at        timestamptz NOT NULL DEFAULT now(),
  UNIQUE (invoice_request_id, kind)
);

-- ---------------------------------------------------------------------
-- FULFILLMENT
-- ---------------------------------------------------------------------

CREATE TABLE shipment (
  id              bigserial PRIMARY KEY,
  order_id        bigint NOT NULL REFERENCES "order"(id) ON DELETE CASCADE,
  carrier         text   NOT NULL,
  tracking_number text   NOT NULL,
  tracking_url    text   NOT NULL DEFAULT '',
  cost_cents      integer NULL CHECK (cost_cents IS NULL OR cost_cents >= 0),
  shipped_at      timestamptz NOT NULL DEFAULT now(),
  delivered_at    timestamptz NULL
);
CREATE UNIQUE INDEX shipment_order_idx ON shipment(order_id);  -- one shipment per order (OA-60, ADR-0051)

-- ---------------------------------------------------------------------
-- TRANSACTIONAL EMAIL OUTBOX  (retry without a broker)
-- ---------------------------------------------------------------------

CREATE TABLE email_outbox (
  id           bigserial PRIMARY KEY,
  to_email     citext  NOT NULL,
  template     text    NOT NULL,
  context      jsonb   NOT NULL DEFAULT '{}'::jsonb,
  order_id     bigint  NULL REFERENCES "order"(id) ON DELETE SET NULL,
  dedupe_key   text    NULL,
  attempts     integer NOT NULL DEFAULT 0,
  sent_at      timestamptz NULL,
  last_error   text    NOT NULL DEFAULT '',
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX email_outbox_dedupe_uq ON email_outbox(dedupe_key)
  WHERE dedupe_key IS NOT NULL;
CREATE INDEX email_outbox_pending_idx ON email_outbox(created_at) WHERE sent_at IS NULL;

-- ---------------------------------------------------------------------
-- SITE SETTINGS
-- ---------------------------------------------------------------------

-- One row, id = 1, edited in the admin. prelaunch_mode hides the public
-- catalog while staff test the live store (G32, ADR-0038).
CREATE TABLE site_setting (
  id             smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  prelaunch_mode boolean  NOT NULL DEFAULT false,
  updated_at     timestamptz NOT NULL DEFAULT now()
);
