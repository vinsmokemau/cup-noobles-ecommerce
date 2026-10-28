"""The carrier contract suite is complete (SPEC.md 10.13, P10-V01)."""

import ast
import re
import socket
from pathlib import Path

import pytest
import pytest_socket

from tests.contract.carrier.driver import MockDriver

SCENARIOS = Path(__file__).with_name("test_scenarios.py")
CAR_IDS = [f"CAR-{n:02d}" for n in range(1, 8)]
TEST_NAME = re.compile(r"test_car_(\d\d)_")


def scenario_ids() -> list[str]:
    tree = ast.parse(SCENARIOS.read_text(encoding="utf-8"))
    matches = (
        TEST_NAME.match(node.name)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    )
    return sorted(f"CAR-{match.group(1)}" for match in matches if match)


def test_p10_v01_all_scenarios_present_and_supported():
    # Every scenario of 10.13 has exactly one test, and the suite has no other.
    assert scenario_ids() == CAR_IDS
    # The mock plays all of them.
    driver = MockDriver()
    assert [car_id for car_id in CAR_IDS if driver.supports(car_id) is not True] == []
    # The scenarios run with sockets disabled (CR-41).
    with pytest.raises(pytest_socket.SocketConnectBlockedError):
        socket.create_connection(("203.0.113.1", 80), timeout=1)
