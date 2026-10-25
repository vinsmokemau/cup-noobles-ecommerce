"""P6-V16: session and CSRF cookie flags under the production settings (T6.2)."""

import importlib.util
from pathlib import Path

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from apps.accounts.models import Customer

pytestmark = pytest.mark.django_db

PROD_SETTINGS = Path(__file__).resolve().parents[3] / "config" / "settings" / "prod.py"
COOKIE_SETTINGS = (
    "SESSION_COOKIE_SECURE",
    "SESSION_COOKIE_HTTPONLY",
    "SESSION_COOKIE_SAMESITE",
    "SESSION_COOKIE_AGE",
    "CSRF_COOKIE_SECURE",
    "CSRF_COOKIE_HTTPONLY",
    "CSRF_COOKIE_SAMESITE",
)
THIRTY_DAYS = 60 * 60 * 24 * 30


@pytest.fixture
def prod_cookie_settings(monkeypatch):
    """The cookie settings `prod.py` resolves to, loaded from its source."""
    for name, value in {
        "SECRET_KEY": "test-only-secret",
        "DATABASE_URL": "postgres://user:pass@db:5432/cupnoobles",
        "ALLOWED_HOSTS": "testserver",
        "CSRF_TRUSTED_ORIGINS": "https://testserver",
        "PAYMENT_PROVIDER": "mercadopago",
        "CARRIER_PROVIDER": "manual",
        "EMAIL_PROVIDER": "resend",
        "MEDIA_STORAGE": "s3",
        "POSTAL_CODE_DATASET": "sepomex",
        "ERROR_TRACKING": "sentry",
        "OWNER_ALERT_EMAIL": "owner@cupnoobles.example",
    }.items():
        monkeypatch.setenv(name, value)
    spec = importlib.util.spec_from_file_location("config.settings.prod", PROD_SETTINGS)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "config.settings"
    spec.loader.exec_module(module)
    return {name: getattr(module, name) for name in COOKIE_SETTINGS}


def test_p6_v16_session_cookie_flags(prod_cookie_settings):
    Customer.objects.create_superuser(email="owner@cupnoobles.test", password="x")
    client = Client()

    with override_settings(**prod_cookie_settings):
        page = client.get(reverse("admin:login"), secure=True)
        login = client.post(
            reverse("admin:login"),
            {"username": "owner@cupnoobles.test", "password": "x"},
            secure=True,
        )

    assert login.status_code == 302
    session = login.cookies["sessionid"]
    assert session["httponly"]
    assert session["secure"]
    assert session["samesite"] == "Lax"
    assert session["max-age"] == THIRTY_DAYS

    # Nuxt reads `csrftoken` to send `X-CSRFToken`, so script must be able to read it.
    csrf = page.cookies["csrftoken"]
    assert not csrf["httponly"]
    assert csrf["secure"]
    assert csrf["samesite"] == "Lax"
