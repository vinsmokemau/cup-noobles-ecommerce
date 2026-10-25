"""CR-09: an order's state changes only through `apply_event` (SPEC.md §4.6)."""

import pytest

from tests.architecture.ast_scan import field_write_violations, scan_apps

STATE_FIELDS = {"state"}
# The scan matches the attribute name, so it also sees `InventoryReservation.state`, which the
# inventory services move held -> committed/released (T4.1).
STATE_ALLOWLIST = {"apps/orders/state_machine.py", "apps/inventory/services.py"}


def check_source(path: str, source: str) -> list[str]:
    """`path` is relative to `api/`, with forward slashes."""
    return field_write_violations(path, source, STATE_FIELDS, STATE_ALLOWLIST)


def test_no_direct_state_assignment_in_the_tree():
    assert scan_apps(STATE_FIELDS, STATE_ALLOWLIST) == []


@pytest.mark.parametrize(
    "source",
    [
        'order.state = "paid"',
        'order.state += "x"',
        'order.state: str = "paid"',
        'order.state, order.total = "paid", 0',
        'setattr(order, "state", "paid")',
        'Order.objects.filter(pk=1).update(state="paid")',
        'def f(o):\n    if o:\n        o.state = "paid"',
    ],
)
def test_state_write_is_found_however_it_is_written(source):
    assert check_source("apps/catalog/x.py", source)


@pytest.mark.parametrize(
    "source",
    [
        "state = 1",
        "x = order.state",
        'setattr(order, "status", 1)',
        'setattr(order, name, "paid")',
        "Order.objects.update(status=1)",
        'print(order.state == "paid")',
    ],
)
def test_reading_state_or_writing_another_field_is_not_flagged(source):
    assert check_source("apps/catalog/x.py", source) == []


def test_the_state_machine_may_write_state():
    assert check_source("apps/orders/state_machine.py", 'order.state = "paid"') == []
    assert check_source("apps/orders/services.py", 'order.state = "paid"')
