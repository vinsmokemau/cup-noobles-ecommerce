"""Test suite settings (§4.6): every provider is its mock, whatever the environment says."""

from .base import *

PAYMENT_PROVIDER = "mock"
CARRIER_PROVIDER = "mock"
EMAIL_PROVIDER = "file"
MEDIA_STORAGE = "local"
POSTAL_CODE_DATASET = "sample"
ERROR_TRACKING = "off"
INVOICE_PROVIDER = "manual"

DEV_TOOLS_ENABLED = True

ALLOWED_HOSTS = ["localhost", "testserver"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:8080"]

# MD5 for speed; a dedicated test asserts that prod.py lists Argon2 first.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# A missing template variable shows in the output.
TEMPLATES[0]["OPTIONS"]["string_if_invalid"] = "⟦MISSING:%s⟧"  # type: ignore[index]
