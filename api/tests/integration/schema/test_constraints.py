"""Database constraints, exercised below the ORM's own validation (SPEC.md Phase 2 Verify)."""

import datetime
import uuid

import pytest
from django.db import IntegrityError, transaction

from tests.factories.accounts import AddressFactory, CustomerFactory
from tests.factories.catalog import (
    CategoryFactory,
    ProductFactory,
    ProductTypeFactory,
    VariantFactory,
)
from tests.factories.inventory import LocationFactory
from tests.factories.invoicing import InvoiceRequestFactory
from tests.factories.orders import OrderFactory, OrderLineFactory
from tests.factories.payments import PaymentFactory, WebhookEventFactory
from tests.factories.shipping import MxStateFactory

pytestmark = pytest.mark.django_db


def rejected(constraint: str):
    """The block must raise IntegrityError naming `constraint`; the transaction survives it."""
    return _Rejected(constraint)


class _Rejected:
    def __init__(self, constraint: str) -> None:
        self._raises = pytest.raises(IntegrityError, match=constraint)
        self._savepoint = transaction.atomic()

    def __enter__(self) -> None:
        self._raises.__enter__()
        self._savepoint.__enter__()

    def __exit__(self, *exc) -> bool:
        self._savepoint.__exit__(*exc)
        return self._raises.__exit__(*exc)


def test_p2_v03_duplicate_variant_options():
    product = ProductFactory()
    VariantFactory(product=product, options={"talla": "L", "color": "negro"})
    with rejected("variant_product_options_uq"):
        VariantFactory(product=product, options={"talla": "L", "color": "negro"})
    # jsonb normalises key order, so the same keys in another order are the same options.
    with rejected("variant_product_options_uq"):
        VariantFactory(product=product, options={"color": "negro", "talla": "L"})
    VariantFactory(product=product, options={"talla": "M", "color": "negro"})
    VariantFactory(options={"talla": "L", "color": "negro"})  # another product


def test_p2_v08_preorder_constraints():
    release = datetime.date(2027, 3, 1)
    with rejected("variant_preorder_needs_date"):
        VariantFactory(is_preorder=True)
    with rejected("variant_preorder_within_limit"):
        VariantFactory(
            is_preorder=True,
            expected_release_date=release,
            preorder_limit=10,
            preorder_committed=11,
        )
    VariantFactory(
        is_preorder=True,
        expected_release_date=release,
        preorder_limit=10,
        preorder_committed=10,
    )


def test_p2_v12_catalog_constraints(raw_sql):
    with rejected("product_active_needs_publish"):
        ProductFactory(status="active", published_at=None)

    category = CategoryFactory()
    with rejected("category_not_self_parent"):
        raw_sql("UPDATE category SET parent_id = id WHERE id = %s", [category.id])

    product_type = ProductTypeFactory()
    insert_product = (
        "INSERT INTO product (product_type_id, slug, name, attributes) "
        "VALUES (%s, %s, 'Producto', %s::jsonb)"
    )
    with rejected("product_attributes_is_object"):
        raw_sql(insert_product, [product_type.id, "attrs-array", "[]"])
    with rejected("product_attributes_is_object"):
        raw_sql(insert_product, [product_type.id, "attrs-scalar", '"texto"'])
    raw_sql(insert_product, [product_type.id, "attrs-object", "{}"])

    product = ProductFactory()
    insert_variant = (
        "INSERT INTO variant (product_id, sku, price_cents, options) "
        "VALUES (%s, %s, 100, %s::jsonb)"
    )
    with rejected("variant_options_is_object"):
        raw_sql(insert_variant, [product.id, "OPT-ARRAY", '["L"]'])
    raw_sql(insert_variant, [product.id, "OPT-OBJECT", "{}"])


def test_p2_v02_reserved_le_on_hand(raw_sql):
    variant = VariantFactory()
    location = LocationFactory()
    insert = (
        "INSERT INTO stock_item (variant_id, location_id, on_hand, reserved) "
        "VALUES (%s, %s, %s, %s)"
    )
    with rejected("stock_reserved_le_on_hand"):
        raw_sql(insert, [variant.id, location.id, 0, 1])
    raw_sql(insert, [variant.id, location.id, 1, 1])


def test_p2_v11_address_constraints(raw_sql):
    customer = CustomerFactory()
    default = AddressFactory(customer=customer, is_default=True)
    with rejected("address_single_default_uq"):
        AddressFactory(customer=customer, is_default=True)
    # A soft-deleted default does not block a new one.
    raw_sql("UPDATE address SET deleted_at = now() WHERE id = %s", [default.id])
    AddressFactory(customer=customer, is_default=True)
    # Another customer has a default of their own.
    AddressFactory(is_default=True)

    state = MxStateFactory()
    for postal_code in ("0670", "0670A"):
        with rejected("address_postal_code_check"):
            AddressFactory(state=state, postal_code=postal_code)
    AddressFactory(state=state, postal_code="06700")


def test_p2_v04_order_total_arithmetic():
    with rejected("order_total_arithmetic"):
        OrderFactory(subtotal_cents=10000, shipping_cents=9900, total_cents=10000)
    with rejected("order_total_arithmetic"):
        OrderFactory(subtotal_cents=10000, discount_cents=500, total_cents=10000)
    OrderFactory(
        subtotal_cents=10000, shipping_cents=9900, discount_cents=500, total_cents=19400
    )


def test_p2_v09_order_fulfillment_target():
    warehouse = LocationFactory()
    address = {"street": "Calle de Prueba", "postal_code": "06700"}
    for method in ("pickup", "delivery"):
        OrderFactory(
            state="draft", fulfillment_method=method
        )  # neither is fine in draft
        with rejected("order_fulfillment_target_complete"):
            OrderFactory(state="pending_payment", fulfillment_method=method)
    OrderFactory(
        state="pending_payment", fulfillment_method="pickup", pickup_location=warehouse
    )
    OrderFactory(
        state="pending_payment", fulfillment_method="delivery", shipping_address=address
    )
    with rejected("order_pickup_has_no_shipping_fee"):
        OrderFactory(
            state="pending_payment",
            fulfillment_method="pickup",
            pickup_location=warehouse,
            subtotal_cents=10000,
            shipping_cents=9900,
            total_cents=19900,
        )


def test_p2_v10_order_line_arithmetic():
    order = OrderFactory()
    with rejected("order_line_total_arithmetic"):
        OrderLineFactory(
            order=order, quantity=2, unit_price_cents=10000, line_total_cents=10000
        )
    with rejected("order_line_fulfilled_le_qty"):
        OrderLineFactory(order=order, quantity=2, fulfilled_quantity=3)
    OrderLineFactory(
        order=order,
        quantity=2,
        unit_price_cents=10000,
        line_total_cents=20000,
        fulfilled_quantity=2,
    )


def test_p2_v13_payment_constraints(raw_sql):
    order = OrderFactory()
    with rejected("payment_refund_le_amount"):
        PaymentFactory(order=order, amount_cents=10000, refunded_cents=10001)
    PaymentFactory(order=order, amount_cents=10000, refunded_cents=10000)
    # Many payments may have no provider id yet; a provider id is unique per provider.
    PaymentFactory(order=order, provider_payment_id=None)
    PaymentFactory(order=order, provider_payment_id=None)
    PaymentFactory(order=order, provider_payment_id="1001")
    with rejected("payment_provider_payment_uq"):
        PaymentFactory(order=order, provider_payment_id="1001")
    PaymentFactory(order=order, provider="otro", provider_payment_id="1001")


def test_p2_v16_webhook_event_uniqueness():
    WebhookEventFactory(external_id="notificacion-1", payload={"data": {"id": "1001"}})
    with rejected("webhook_event_provider_topic_external_id_key"):
        WebhookEventFactory(external_id="notificacion-1")
    # Two notifications about one payment are two deliveries (9.A rule 4).
    WebhookEventFactory(external_id="notificacion-2", payload={"data": {"id": "1001"}})
    WebhookEventFactory(topic="merchant_order", external_id="notificacion-1")


def test_p2_v17_invoice_constraints(raw_sql):
    request = InvoiceRequestFactory()
    with rejected("invoice_request_order_id_key"):
        InvoiceRequestFactory(order=request.order)
    with rejected("invoice_issued_complete"):
        InvoiceRequestFactory(status="issued", issued_at=None)
    with rejected("invoice_issued_complete"):
        InvoiceRequestFactory(status="issued", cfdi_uuid=uuid.uuid4())
    InvoiceRequestFactory(
        status="issued",
        cfdi_uuid=uuid.uuid4(),
        issued_at=datetime.datetime.now(datetime.UTC),
    )
    with rejected("invoice_request_fiscal_postal_code_check"):
        InvoiceRequestFactory(fiscal_postal_code="0670")

    insert = (
        "INSERT INTO invoice_document (invoice_request_id, kind, filename, content, sha256, size_bytes) "
        "VALUES (%s, %s, 'factura', 'x', repeat('a', 64), %s)"
    )
    raw_sql(insert, [request.id, "pdf", 1])
    with rejected("invoice_document_invoice_request_id_kind_key"):
        raw_sql(insert, [request.id, "pdf", 1])
    raw_sql(insert, [request.id, "xml", 5242880])  # exactly 5 MB is accepted
    other = InvoiceRequestFactory()
    with rejected("invoice_document_size_bytes_check"):
        raw_sql(insert, [other.id, "pdf", 5242881])
