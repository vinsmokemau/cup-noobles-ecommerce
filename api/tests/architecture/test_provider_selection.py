"""CR-18, CR-20, CR-21: implementations are chosen only by the registry (SPEC.md §4.3)."""

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from apps.core import providers

API_DIR = Path(__file__).resolve().parents[2]
REGISTRY = "apps/core/providers.py"

# Adapter packages and the implementation modules inside them.
ADAPTER_PACKAGES = (
    "apps.payments",
    "apps.shipping.carriers",
    "apps.notifications.email",
    "apps.core.errors",
    "apps.invoicing",
)
IMPLEMENTATION_MODULES = (
    "mock",
    "mercadopago",
    "manual",
    "file",
    "resend",
    "ses",
    "null",
    "sentry",
)
IMPLEMENTATIONS = {
    f"{package}.{module}"
    for package in ADAPTER_PACKAGES
    for module in IMPLEMENTATION_MODULES
}


def module_name(path: str) -> str:
    return path.removesuffix(".py").removesuffix("/__init__").replace("/", ".")


def imported_modules(path: str, source: str) -> set[str]:
    """Every dotted module the file imports, plus `from pkg import name` candidates."""
    package = module_name(path)
    if not path.endswith("/__init__.py"):
        package = package.rpartition(".")[0]
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                anchor = package.split(".")
                anchor = anchor[: len(anchor) - node.level + 1]
                base = ".".join([*anchor, *([base] if base else [])])
            found.add(base)
            found.update(f"{base}.{alias.name}" for alias in node.names)
    return found


def implementation_imports(path: str, source: str) -> list[str]:
    """`path` is relative to `api/`, with forward slashes."""
    if path == REGISTRY:
        return []
    return [
        f"{path} imports {module}"
        for module in sorted(imported_modules(path, source))
        if any(
            module == impl or module.startswith(f"{impl}.") for impl in IMPLEMENTATIONS
        )
    ]


def scan_tree() -> list[str]:
    violations = []
    for root in ("apps", "config"):
        for file in sorted((API_DIR / root).rglob("*.py")):
            path = file.relative_to(API_DIR).as_posix()
            violations += implementation_imports(path, file.read_text(encoding="utf-8"))
    return violations


def test_p1_v19_implementations_imported_only_by_registry():
    assert scan_tree() == []


def test_p1_v19_selftest_flags_implementation_import_outside_registry():
    flagged = implementation_imports(
        "apps/orders/services.py", "import apps.payments.mock"
    )

    assert flagged == ["apps/orders/services.py imports apps.payments.mock"]


@pytest.mark.parametrize(
    ("path", "source"),
    [
        ("apps/orders/services.py", "from apps.payments.mock import X"),
        ("apps/orders/services.py", "from apps.payments import mock"),
        ("apps/orders/services.py", "from apps.shipping.carriers.manual import X"),
        (
            "apps/orders/services.py",
            "def f():\n    from apps.core.errors.sentry import X",
        ),
        ("apps/payments/views.py", "from .mock import X"),
        ("apps/payments/views.py", "from . import mercadopago"),
        ("apps/notifications/email/sender.py", "from .file import X"),
        ("apps/notifications/tasks.py", "from .email import resend"),
        ("apps/invoicing/admin.py", "from .manual import X"),
    ],
)
def test_implementation_import_is_found_however_it_is_written(path, source):
    assert implementation_imports(path, source)


@pytest.mark.parametrize(
    ("path", "source"),
    [
        (REGISTRY, "import apps.payments.mock"),
        ("apps/payments/views.py", "from .base import PaymentProvider"),
        ("apps/orders/services.py", "from apps.payments.base import PaymentProvider"),
        ("apps/orders/services.py", "from apps.core import providers"),
        # `manual` and `file` are implementations only inside an adapter package.
        ("apps/orders/services.py", "from apps.orders import manual"),
    ],
)
def test_registry_and_interface_imports_are_allowed(path, source):
    assert implementation_imports(path, source) == []


_PROD_ENV = {
    "SECRET_KEY": "test-only-secret",
    "DATABASE_URL": "postgres://user:pass@db:5432/cupnoobles",
    "ALLOWED_HOSTS": "cupnoobles.example",
    "CSRF_TRUSTED_ORIGINS": "https://cupnoobles.example",
    "PAYMENT_PROVIDER": "mercadopago",
    "CARRIER_PROVIDER": "manual",
    "EMAIL_PROVIDER": "resend",
    "MEDIA_STORAGE": "s3",
    "POSTAL_CODE_DATASET": "sepomex",
    "ERROR_TRACKING": "sentry",
}

REGISTRY_SWITCHES = [
    ("PAYMENT_PROVIDER", "payment_provider", providers.PAYMENT_IMPLS),
    ("CARRIER_PROVIDER", "carrier", providers.CARRIER_IMPLS),
    ("EMAIL_PROVIDER", "email_sender", providers.EMAIL_IMPLS),
    ("ERROR_TRACKING", "error_reporter", providers.ERROR_IMPLS),
    ("INVOICE_PROVIDER", "invoicer", providers.INVOICE_IMPLS),
]

# Registry entries whose implementation module is a Part A mock.
MOCK_VALUES = [
    (setting, value)
    for setting, _, impls in REGISTRY_SWITCHES
    for value, dotted in impls.items()
    if dotted.split(".")[-2] in {"mock", "file"}
]


def start_prod(overrides: dict[str, str]) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in _PROD_ENV}
    env.update(_PROD_ENV | overrides, DJANGO_SETTINGS_MODULE="config.settings.prod")
    return subprocess.run(
        [sys.executable, "-c", "import django; django.setup()"],
        check=False,
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_mock_values_are_derived_from_the_registry():
    assert set(MOCK_VALUES) == {
        ("PAYMENT_PROVIDER", "mock"),
        ("CARRIER_PROVIDER", "mock"),
        ("EMAIL_PROVIDER", "file"),
    }


def test_prod_starts_when_no_value_is_a_mock():
    run = start_prod({})

    assert run.returncode == 0, run.stderr


@pytest.mark.parametrize(
    ("setting", "value"), MOCK_VALUES, ids=[s for s, _ in MOCK_VALUES]
)
def test_prod_does_not_accept_a_mock_value(setting, value):
    run = start_prod({setting: value})

    assert run.returncode != 0
    assert "ImproperlyConfigured" in run.stderr


@pytest.mark.parametrize(
    ("setting", "factory", "_impls"),
    REGISTRY_SWITCHES,
    ids=[s for s, _, _ in REGISTRY_SWITCHES],
)
def test_unknown_value_raises_improperly_configured(
    use_provider, setting, factory, _impls
):
    from django.core.exceptions import ImproperlyConfigured

    use_provider(setting, "unknown")

    with pytest.raises(ImproperlyConfigured):
        getattr(providers, factory)()
