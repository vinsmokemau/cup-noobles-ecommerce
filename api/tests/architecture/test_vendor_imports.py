"""CR-19: a vendor package is imported only by its adapter module (SPEC.md §4.3)."""

import ast
from pathlib import Path

import pytest

API_DIR = Path(__file__).resolve().parents[2]

VENDOR_ALLOWLIST = {
    "mercadopago": {"apps/payments/mercadopago.py"},
    "resend": {"apps/notifications/email/resend.py"},
    "boto3": {"apps/notifications/email/ses.py"},
    "botocore": {"apps/notifications/email/ses.py"},
    "storages": set(),  # referenced only as a dotted string in STORAGES
    "sentry_sdk": {"apps/core/errors/sentry.py"},
    "requests": {"apps/payments/mercadopago.py"},
    "httpx": {"apps/payments/mercadopago.py"},
}


def imported_packages(source: str) -> set[str]:
    """Top-level package of every absolute import, wherever it sits in the file."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return found


def vendor_violations(path: str, source: str) -> list[str]:
    """`path` is relative to `api/`, with forward slashes."""
    return [
        f"{path} imports {package}"
        for package in sorted(imported_packages(source) & VENDOR_ALLOWLIST.keys())
        if path not in VENDOR_ALLOWLIST[package]
    ]


def scan_tree() -> list[str]:
    violations = []
    for root in ("apps", "config"):
        for file in sorted((API_DIR / root).rglob("*.py")):
            path = file.relative_to(API_DIR).as_posix()
            violations += vendor_violations(path, file.read_text(encoding="utf-8"))
    return violations


def test_p1_v12_vendor_imports_confined():
    assert scan_tree() == []


def test_p1_v12_selftest_flags_vendor_import_outside_its_adapter():
    assert vendor_violations("apps/orders/services.py", "import mercadopago") == [
        "apps/orders/services.py imports mercadopago"
    ]


@pytest.mark.parametrize(
    "source",
    [
        "import mercadopago.config",
        "from mercadopago import SDK",
        "def pay():\n    import mercadopago",
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    import mercadopago",
    ],
)
def test_vendor_import_is_found_however_it_is_written(source):
    assert vendor_violations("apps/orders/services.py", source)


def test_vendor_import_is_allowed_in_its_adapter_only():
    assert vendor_violations("apps/payments/mercadopago.py", "import mercadopago") == []
    assert vendor_violations("apps/payments/mercadopago.py", "import resend")
    assert vendor_violations("apps/core/errors/sentry.py", "import mercadopago")


def test_storages_is_never_imported():
    assert vendor_violations("apps/core/media.py", "import storages")


def test_relative_import_of_a_local_module_is_not_a_vendor_import():
    assert vendor_violations("apps/orders/services.py", "from . import requests") == []


def test_p9_v06_payment_adapters_clean():
    from apps.core.providers import PAYMENT_IMPLS

    source = (API_DIR / "apps/payments/mock.py").read_text(encoding="utf-8")
    assert imported_packages(source) & VENDOR_ALLOWLIST.keys() == set()
    assert vendor_violations("apps/payments/mock.py", source) == []

    # Every entry names a class in a module under apps/payments. The Mercado Pago module is
    # written in Phase 16, so only the entries whose module exists are imported.
    for dotted in PAYMENT_IMPLS.values():
        module, _, name = dotted.rpartition(".")
        assert module.startswith("apps.payments.") and name
        if (API_DIR / (module.replace(".", "/") + ".py")).exists():
            from django.utils.module_loading import import_string

            assert isinstance(import_string(dotted), type)
