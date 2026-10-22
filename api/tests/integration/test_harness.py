"""The test harness itself: the Postgres guard and the offline socket guard (§4.6)."""

import socket
from pathlib import Path

import pytest
from pytest_socket import SocketBlockedError, SocketConnectBlockedError

from tests.conftest import POSTGRES_GUARD_MESSAGE

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


def _database_address() -> tuple[str, int]:
    from django.conf import settings

    db = settings.DATABASES["default"]
    return db["HOST"] or "db", int(db["PORT"] or 5432)
