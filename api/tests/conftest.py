import os
from contextlib import ExitStack

import pytest
import time_machine
from django.db import connection
from hypothesis import HealthCheck
from hypothesis import settings as hypothesis_settings
from rest_framework.test import APIClient

from apps.core import providers

pytest_plugins = ["pytester"]

POSTGRES_GUARD_MESSAGE = (
    "Tests run on PostgreSQL only (CR-40): "
    "DATABASE_URL must point at the compose `db` service, not {vendor}."
)

hypothesis_settings.register_profile(
    "dev", max_examples=100, suppress_health_check=[HealthCheck.too_slow]
)
hypothesis_settings.register_profile(
    "ci", max_examples=1000, derandomize=True, deadline=None
)
hypothesis_settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))


@pytest.fixture(scope="session", autouse=True)
def _require_postgres():
    """Abort the whole run unless the database is PostgreSQL (CR-40)."""
    if connection.vendor != "postgresql":
        pytest.exit(
            POSTGRES_GUARD_MESSAGE.format(vendor=connection.vendor), returncode=3
        )


@pytest.fixture(autouse=True)
def _isolated_file_stores(settings, tmp_path):
    """Emails and mock-provider state go to a per-test directory (§4.6)."""
    settings.EMAIL_FILE_DIR = str(tmp_path / "emails")
    settings.MOCK_STORE_DIR = str(tmp_path / "mock_store")


@pytest.fixture
def api_client() -> APIClient:
    """An anonymous DRF client that enforces CSRF, so CSRF is under test."""
    return APIClient(enforce_csrf_checks=True)


@pytest.fixture
def auth_client():
    """`auth_client(customer)`: a CSRF-enforcing client logged in through the session."""

    def make(user) -> APIClient:
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(user)
        return client

    return make


class Clock:
    """Moves time for one test: `clock.travel("2026-01-01T12:00:00Z")`."""

    def __init__(self, stack: ExitStack) -> None:
        self._stack = stack

    def travel(self, destination, *, tick: bool = False) -> time_machine.travel:
        traveller = time_machine.travel(destination, tick=tick)
        self._stack.enter_context(traveller)
        return traveller


@pytest.fixture
def clock():
    with ExitStack() as stack:
        yield Clock(stack)


@pytest.fixture
def use_provider(settings):
    """Switch a provider setting for one test: `use_provider("PAYMENT_PROVIDER", "mock")`.

    Applies the setting override and clears the registry caches, so no chosen
    implementation leaks into another test (SPEC.md §4.3).
    """

    def apply(setting: str, value: str) -> None:
        setattr(settings, setting, value)
        providers.clear_provider_caches()

    yield apply
    providers.clear_provider_caches()
