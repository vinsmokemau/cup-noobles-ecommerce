import pytest

from apps.notifications.content import TEMPLATES, UnknownTemplate
from apps.notifications.rendering import render_email
from tests.integration.notifications.conftest import R1_TEMPLATES

pytestmark = pytest.mark.django_db


def test_the_registry_holds_exactly_the_r1_templates():
    assert set(TEMPLATES) == set(R1_TEMPLATES)


@pytest.mark.parametrize("template", R1_TEMPLATES)
def test_p11_v01_every_template_renders(template, template_context, snapshot):
    context, order = template_context(template)

    email = render_email(template, context, order)

    # The factory numbers orders in sequence; the snapshot must not depend on test order.
    def stable(value):
        return value.replace(order.number, "CN-2026-000000")

    assert email.html.strip() and email.text.strip()
    for leak in ("{{", "{%", "⟦MISSING"):
        assert leak not in email.html + email.text + email.subject, leak
    assert {
        "subject": stable(email.subject),
        "text": stable(email.text),
        "html": stable(email.html),
    } == snapshot


@pytest.mark.parametrize("template", R1_TEMPLATES)
def test_p11_v04_no_template_syntax_leaks(template, template_context):
    context, order = template_context(template)

    email = render_email(template, context, order)

    for leak in ("{{", "{%", "⟦MISSING"):
        assert leak not in email.html, leak
        assert leak not in email.subject, leak
    assert '<html lang="es-MX"' in email.html
    assert order.number in email.subject


@pytest.mark.parametrize("template", R1_TEMPLATES)
def test_every_slot_of_the_layout_is_filled(template, template_context):
    context, order = template_context(template)

    email = render_email(template, context, order)

    assert all(value.strip() for value in email.content.slots.values())
    assert (
        len(email.content.slots) == 13
    )  # the 18 slots less the five of the repeated rows
    assert len(email.content.items) == 2 and email.content.totals


def test_order_lines_and_totals_fill_the_rows_and_are_escaped(template_context):
    context, order = template_context("order_confirmation")

    html = render_email("order_confirmation", context, order).html

    assert "Caja de sobres &amp; más (Español)" in html
    assert "x2" in html and "$200.00" in html
    assert "Dados" in html and "$50.00" in html
    for label, amount in (
        ("Subtotal", "$250.00"),
        ("Envío", "$99.00"),
        ("Total", "$349.00"),
    ):
        assert label in html and amount in html


def test_oxxo_voucher_names_the_deadline_in_the_store_timezone(template_context):
    context, order = template_context("oxxo_voucher")

    html = render_email("oxxo_voucher", context, order).html

    assert "4 de marzo de 2026 a las 12:00 p.m." in html
    assert context["voucher_url"] in html


def test_order_shipped_without_tracking_url_falls_back_to_the_lookup(template_context):
    context, order = template_context("order_shipped")
    context["tracking_url"] = ""

    html = render_email("order_shipped", context, order).html

    assert "/rastrear" in html and "paqueteria.example.test" not in html


def test_order_cancelled_says_whether_a_refund_was_requested(template_context):
    context, order = template_context("order_cancelled")
    unpaid = render_email("order_cancelled", context, order).html
    context["refunded_cents"] = 34900
    paid = render_email("order_cancelled", context, order).html

    assert "No se hizo ningún cargo" in unpaid
    assert "$349.00" in paid and "No se hizo ningún cargo" not in paid


def test_an_unknown_template_is_an_error(template_context):
    _, order = template_context("order_expired")

    with pytest.raises(UnknownTemplate):
        render_email("verify_email", {}, order)
