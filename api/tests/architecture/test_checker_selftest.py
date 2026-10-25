"""P1-V05: the state and stock checkers detect what they exist to detect."""

from tests.architecture.test_no_direct_state_assignment import (
    check_source as check_state,
)
from tests.architecture.test_stock_mutation_boundary import (
    check_source as check_stock,
)

STATE_SNIPPETS = [
    'order.state = "paid"',
    'setattr(o, "state", "paid")',
    'Order.objects.filter(pk=1).update(state="paid")',
]
STOCK_SNIPPET = "stock_item.on_hand -= 1"


def test_p1_v05_state_and_stock_violations_detected():
    for snippet in STATE_SNIPPETS:
        assert check_state("apps/catalog/x.py", snippet), snippet
    assert check_stock("apps/catalog/x.py", STOCK_SNIPPET)
    assert check_stock("apps/orders/services.py", STOCK_SNIPPET)

    # Outside its allowlisted module the same write is a violation.
    assert check_state("apps/orders/services.py", STATE_SNIPPETS[0])
    assert check_stock("apps/orders/state_machine.py", STOCK_SNIPPET)

    # In its allowlisted module it is not.
    for snippet in STATE_SNIPPETS:
        assert check_state("apps/orders/state_machine.py", snippet) == []
    assert check_stock("apps/inventory/services.py", STOCK_SNIPPET) == []
