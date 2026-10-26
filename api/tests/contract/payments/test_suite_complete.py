"""The payment contract suite is complete (SPEC.md 9.13, P9-V01)."""

import ast
import re
import socket
from pathlib import Path

import pytest
import pytest_socket

from tests.contract.payments.driver import MockDriver

SCENARIOS = Path(__file__).with_name("test_scenarios.py")
PAY_IDS = [f"PAY-{n:02d}" for n in range(1, 20)]
TEST_NAME = re.compile(r"test_pay_(\d\d)_")


def scenario_ids() -> list[str]:
    tree = ast.parse(SCENARIOS.read_text(encoding="utf-8"))
    matches = (
        TEST_NAME.match(node.name)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    )
    return sorted(f"PAY-{match.group(1)}" for match in matches if match)


def test_p9_v01_all_scenarios_present_and_supported():
    # Every scenario of 9.13 has exactly one test, and the suite has no other.
    assert scenario_ids() == PAY_IDS
    # The mock plays all of them.
    driver = MockDriver()
    assert [pay_id for pay_id in PAY_IDS if driver.supports(pay_id) is not True] == []
    # The scenarios run with sockets disabled (CR-41).
    with pytest.raises(pytest_socket.SocketConnectBlockedError):
        socket.create_connection(("203.0.113.1", 80), timeout=1)
