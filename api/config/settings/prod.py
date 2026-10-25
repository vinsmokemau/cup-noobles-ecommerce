"""Production: no mocks, no dev tools, HTTPS only (CR-20, REQ-040)."""

from django.core.exceptions import ImproperlyConfigured

from .base import *
from .base import env

DEBUG = False
DEV_TOOLS_ENABLED = False  # forced, whatever the environment says

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")

SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Provider switches have no default here, and a mock value stops startup.
PAYMENT_PROVIDER = env.str("PAYMENT_PROVIDER")
CARRIER_PROVIDER = env.str("CARRIER_PROVIDER")
EMAIL_PROVIDER = env.str("EMAIL_PROVIDER")
MEDIA_STORAGE = env.str("MEDIA_STORAGE")
POSTAL_CODE_DATASET = env.str("POSTAL_CODE_DATASET")
ERROR_TRACKING = env.str("ERROR_TRACKING")
INVOICE_PROVIDER = env.str("INVOICE_PROVIDER", default="manual")  # not a mock (§4.3)

# No default: the owner's monitored inbox (G38).
OWNER_ALERT_EMAIL = env.str("OWNER_ALERT_EMAIL")

_MOCK_VALUES = {
    "PAYMENT_PROVIDER": "mock",
    "CARRIER_PROVIDER": "mock",
    "EMAIL_PROVIDER": "file",
}
for _switch, _mock in _MOCK_VALUES.items():
    if globals()[_switch] == _mock:
        raise ImproperlyConfigured(
            f"{_switch}={_mock!r} is a mock and is not allowed in production"
        )
