"""The test harness itself: the Postgres guard, the offline socket guard (§4.6) and the lock
that keeps two runs out of one test database (G81)."""

import socket
from pathlib import Path

import pytest
from django.db import connection
from pytest_socket import SocketBlockedError, SocketConnectBlockedError

from tests.conftest import (
    POSTGRES_GUARD_MESSAGE,
    TEST_DATABASE_BUSY_MESSAGE,
    DatabaseBusy,
    lock_test_database,
)

API_DIR = Path(__file__).resolve().parents[2]
CONFTEST = API_DIR / "tests" / "conftest.py"


def test_p1_v04_sqlite_aborts_suite(pytester, monkeypatch):
    pytester.makeini(
        "[pytest]\n"
        "DJANGO_SETTINGS_MODULE = config.settings.test\n"
        f"pythonpath = {API_DIR.as_posix()}\n"
    )
    pytester.makeconftest(CONFTEST.read_text(encoding="utf-8"))
    pytester.makepyfile(test_inner="def test_inner():\n    assert True\n")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///inner.sqlite3")
    monkeypatch.setenv("SECRET_KEY", "test-only-secret")

    result = pytester.runpytest_subprocess("-p", "no:cacheprovider")

    assert result.ret != 0
    result.stdout.fnmatch_lines([f"*{POSTGRES_GUARD_MESSAGE.split('{')[0]}*"])
    result.stdout.no_fnmatch_line("*test_inner.py::test_inner PASSED*")
    assert "1 passed" not in result.stdout.str()


def test_p1_v13_external_socket_blocked():
    with pytest.raises((SocketBlockedError, SocketConnectBlockedError)):
        socket.create_connection(("example.com", 443))

    host, port = _database_address()
    with socket.create_connection((host, port), timeout=5):
        pass


@pytest.mark.django_db
def test_g81_a_second_run_on_the_same_test_database_is_refused(pytester, monkeypatch):
    """This run holds the lock of its test database (the `django_db` mark set it up), so a
    second run started now stops at its first database test instead of waiting on this one."""
    pytester.makeini(
        "[pytest]\n"
        "DJANGO_SETTINGS_MODULE = config.settings.test\n"
        f"pythonpath = {API_DIR.as_posix()}\n"
    )
    pytester.makeconftest(CONFTEST.read_text(encoding="utf-8"))
    pytester.makepyfile(
        test_inner=(
            "import pytest\n\n\n"
            "@pytest.mark.django_db\n"
            "def test_inner():\n"
            "    assert True\n"
        )
    )
    monkeypatch.setenv("SECRET_KEY", "test-only-secret")

    result = pytester.runpytest_subprocess("-p", "no:cacheprovider")

    assert result.ret != 0
    # Inside a test the configured name is already the test database's.
    busy = TEST_DATABASE_BUSY_MESSAGE.format(name=connection.settings_dict["NAME"])
    result.stdout.fnmatch_lines([f"*{busy}*"])
    assert "1 passed" not in result.stdout.str()


def test_g81_the_lock_is_free_again_once_its_holder_is_gone():
    name = "test_g81_no_such_database"  # a name of its own: no run holds this one
    first = lock_test_database(name)
    try:
        with pytest.raises(DatabaseBusy, match=name):
            lock_test_database(name)
    finally:
        # What PostgreSQL does by itself when a run ends or is killed.
        first.close()

    lock_test_database(name).close()


def _database_address() -> tuple[str, int]:
    from django.conf import settings

    db = settings.DATABASES["default"]
    return db["HOST"] or "db", int(db["PORT"] or 5432)
