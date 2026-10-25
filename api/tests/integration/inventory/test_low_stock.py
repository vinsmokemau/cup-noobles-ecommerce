from io import StringIO

import pytest
from django.core.management import call_command
from django.test import override_settings

from apps.notifications.models import EmailOutbox
from tests.factories.inventory import stocked_variant

pytestmark = pytest.mark.django_db

OWNER = "owner-alerts@cupnoobles.test"


def run_report() -> str:
    out = StringIO()
    call_command("low_stock_report", stdout=out)
    return out.getvalue()


@override_settings(OWNER_ALERT_EMAIL=OWNER)
def test_p4_v17_low_stock_report_boundary():
    # G2 and G38 are implemented as proposed and pass, so this carries no xfail (see the report).
    # on_hand 4 - safety 2 = available 2 == safety_stock: listed. on_hand 5 gives 3: not listed.
    at_limit = stocked_variant(on_hand=4, safety_stock=2)
    above = stocked_variant(on_hand=5, safety_stock=2)

    run_report()

    row = EmailOutbox.objects.get()
    assert row.to_email == OWNER
    assert row.template == "low_stock_report"
    assert row.sent_at is None
    listed = {item["sku"]: item for item in row.context["items"]}
    assert set(listed) == {at_limit.sku}
    assert above.sku not in listed
    assert listed[at_limit.sku]["available"] == 2
    assert listed[at_limit.sku]["safety_stock"] == 2


def test_low_stock_report_lists_sold_out_and_counts_holds():
    from tests.factories.inventory import holding_order

    sold_out = stocked_variant(on_hand=0)
    held = stocked_variant(on_hand=3)
    holding_order(held, 3)
    plenty = stocked_variant(on_hand=10)

    run_report()

    skus = {item["sku"] for item in EmailOutbox.objects.get().context["items"]}
    assert skus == {sold_out.sku, held.sku}
    assert plenty.sku not in skus


def test_low_stock_report_queues_nothing_when_all_is_well(settings):
    stocked_variant(on_hand=10, safety_stock=1)

    assert "nothing" in run_report()

    assert not EmailOutbox.objects.exists()


def test_low_stock_report_runs_twice_a_day_without_a_second_email():
    stocked_variant(on_hand=0)

    run_report()
    run_report()

    assert EmailOutbox.objects.count() == 1


def test_owner_alert_email_defaults_to_a_test_address(settings):
    assert settings.OWNER_ALERT_EMAIL.endswith(".test")
