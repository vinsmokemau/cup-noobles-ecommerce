import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

API_DIR = Path(__file__).resolve().parents[3]

# Variables that change what a settings module resolves to; a run never inherits them.
_SCRUBBED = (
    "SECRET_KEY",
    "DATABASE_URL",
    "ALLOWED_HOSTS",
    "CSRF_TRUSTED_ORIGINS",
    "DEV_TOOLS_ENABLED",
    "SECURE_HSTS_SECONDS",
    "PAYMENT_PROVIDER",
    "CARRIER_PROVIDER",
    "EMAIL_PROVIDER",
    "MEDIA_STORAGE",
    "POSTAL_CODE_DATASET",
    "ERROR_TRACKING",
    "INVOICE_PROVIDER",
    "OWNER_ALERT_EMAIL",
)

_PROGRAM = """
import json, sys
import django
from django.conf import settings
django.setup()
print(json.dumps({name: getattr(settings, name) for name in sys.argv[1:]}))
"""

_SECRETS_ENV = {
    "SECRET_KEY": "test-only-secret",
    "DATABASE_URL": "postgres://user:pass@db:5432/cupnoobles",
}

_PROD_ENV = {
    **_SECRETS_ENV,
    "ALLOWED_HOSTS": "cupnoobles.example",
    "CSRF_TRUSTED_ORIGINS": "https://cupnoobles.example",
    "PAYMENT_PROVIDER": "mercadopago",
    "CARRIER_PROVIDER": "manual",
    "EMAIL_PROVIDER": "resend",
    "MEDIA_STORAGE": "s3",
    "POSTAL_CODE_DATASET": "sepomex",
    "ERROR_TRACKING": "sentry",
    "OWNER_ALERT_EMAIL": "owner@cupnoobles.example",
}


@dataclass
class SettingsRun:
    returncode: int
    stdout: str
    stderr: str

    @property
    def values(self) -> dict:
        return json.loads(self.stdout)


RunSettings = Callable[[str, dict[str, str], tuple[str, ...]], SettingsRun]


@pytest.fixture
def run_settings() -> RunSettings:
    """Run `django.setup()` in a subprocess with exactly the given environment."""

    def run(
        module: str, env: dict[str, str], names: tuple[str, ...] = ()
    ) -> SettingsRun:
        child_env = {k: v for k, v in os.environ.items() if k not in _SCRUBBED}
        child_env.update(env)
        child_env["DJANGO_SETTINGS_MODULE"] = module
        done = subprocess.run(
            [sys.executable, "-c", _PROGRAM, *names],
            check=False,
            cwd=API_DIR,
            env=child_env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return SettingsRun(done.returncode, done.stdout, done.stderr)

    return run


@pytest.fixture
def secrets_env() -> dict[str, str]:
    """The environment dev and test need: secrets only, every switch left to its default."""
    return dict(_SECRETS_ENV)


@pytest.fixture
def prod_env() -> dict[str, str]:
    """A complete, valid production environment."""
    return dict(_PROD_ENV)
