"""P15-V11 (T15.3): the seeds and the dev endpoints do not exist in production.

The production half runs in a subprocess under `config.settings.prod`, with `DEV_TOOLS_ENABLED=true`
in its environment, which `prod.py` overrides (P1-V16). Its database address is not a real one:
a guard that let a seed through would fail on the connection, never write anywhere.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

API_DIR = Path(__file__).resolve().parents[3]

# A complete production environment (the same shape as tests/unit/core/conftest.py).
_PROD_ENV = {
    "DJANGO_SETTINGS_MODULE": "config.settings.prod",
    "SECRET_KEY": "test-only-secret",
    "DATABASE_URL": "postgres://nobody:nothing@database.invalid:5432/none",
    "ALLOWED_HOSTS": "cupnoobles.example",
    "CSRF_TRUSTED_ORIGINS": "https://cupnoobles.example",
    "PAYMENT_PROVIDER": "mercadopago",
    "CARRIER_PROVIDER": "manual",
    "EMAIL_PROVIDER": "resend",
    "MEDIA_STORAGE": "s3",
    "POSTAL_CODE_DATASET": "sepomex",
    "ERROR_TRACKING": "sentry",
    "INVOICE_PROVIDER": "manual",
    "OWNER_ALERT_EMAIL": "owner@cupnoobles.example",
    "DEFAULT_FROM_EMAIL": "noreply@cupnoobles.example",
    "EMAIL_REPLY_TO": "tienda@cupnoobles.example",
    "DEV_TOOLS_ENABLED": "true",
}

_PROGRAM = """
import json
import django
django.setup()
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client

report = {"DEV_TOOLS_ENABLED": settings.DEV_TOOLS_ENABLED, "commands": {}, "routes": {}}
for name in ("seed_demo", "seed_e2e"):
    try:
        call_command(name)
        report["commands"][name] = "ran"
    except CommandError as error:
        report["commands"][name] = f"CommandError: {error}"
client = Client()
for method, path in (
    ("post", "/dev/test/run/"),
    ("get", "/dev/test/inventory/DEMO-TCG-CAJA/"),
    ("get", "/dev/test/orders/?email=demo@cupnoobles.test"),
    ("post", "/dev/test/prelaunch/"),
):
    response = getattr(client, method)(
        path,
        data={"command": "advance_orders"} if method == "post" else None,
        content_type="application/json",
        secure=True,
        headers={"host": "cupnoobles.example"},
    )
    report["routes"][path] = response.status_code
print(json.dumps(report))
"""


def run_under_prod() -> dict:
    env = {k: v for k, v in os.environ.items() if k not in _PROD_ENV}
    env.update(_PROD_ENV)
    done = subprocess.run(
        [sys.executable, "-c", _PROGRAM],
        check=False,
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


@pytest.mark.django_db
def test_p15_v11_seed_and_runner_refuse_in_prod(client):
    report = run_under_prod()

    assert report["DEV_TOOLS_ENABLED"] is False
    assert report["commands"] == {
        "seed_demo": "CommandError: seed_demo runs only where DEV_TOOLS_ENABLED is on",
        "seed_e2e": "CommandError: seed_e2e runs only where DEV_TOOLS_ENABLED is on",
    }
    assert report["routes"] == {
        "/dev/test/run/": 404,
        "/dev/test/inventory/DEMO-TCG-CAJA/": 404,
        "/dev/test/orders/?email=demo@cupnoobles.test": 404,
        "/dev/test/prelaunch/": 404,
    }

    # Where the runner does exist, only its list runs: a seed, a wipe and another action of an
    # allowed command are all refused.
    for command in ("seed_demo", "flush", "mock_payments reset", "mock_payments"):
        refused = client.post(
            "/dev/test/run/", {"command": command}, content_type="application/json"
        )
        assert refused.status_code == 400, command
        assert command not in refused.json()["commands"]
