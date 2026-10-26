"""Settings shared by every environment (SPEC.md §4.3, §4.7).

Every secret comes from the environment (CR-50). The provider switches are read
here; a mock is only their default, and `prod.py` re-reads them with no default.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()

# Secrets and connection strings: required, no default (CR-50).
SECRET_KEY = env.str("SECRET_KEY")
DATABASES = {"default": env.db("DATABASE_URL")}

# Provider switches (§4.3). The defaults are the Part A mocks (CR-20).
PAYMENT_PROVIDER = env.str("PAYMENT_PROVIDER", default="mock")
CARRIER_PROVIDER = env.str("CARRIER_PROVIDER", default="mock")
EMAIL_PROVIDER = env.str("EMAIL_PROVIDER", default="file")
MEDIA_STORAGE = env.str("MEDIA_STORAGE", default="local")
POSTAL_CODE_DATASET = env.str("POSTAL_CODE_DATASET", default="sample")
ERROR_TRACKING = env.str("ERROR_TRACKING", default="off")
INVOICE_PROVIDER = env.str("INVOICE_PROVIDER", default="manual")

# Business settings (§4.7). The defaults are the D6 and D7 stand-ins of §2.5; `check_placeholders`
# fails while a value still equals its default, so each needs the owner's decision before launch.
# How long T1 holds stock and the payment window of a new order, before the method is known
# (G11, §4.7). 30 minutes in Part A and Part B.
RESERVATION_TTL_CARD_MINUTES = env.int("RESERVATION_TTL_CARD_MINUTES", default=30)
RESERVATION_TTL_SPEI_HOURS = env.int("RESERVATION_TTL_SPEI_HOURS", default=4)
RESERVATION_TTL_OXXO_HOURS = env.int("RESERVATION_TTL_OXXO_HOURS", default=72)
PAYMENT_INSTALLMENT_OPTIONS = env.list(
    "PAYMENT_INSTALLMENT_OPTIONS", cast=int, default=[3, 6]
)

# Days the purchase-limit guard looks back (G31, D15). The owner has not given the length, so there
# is no default: checkout refuses to run while a variant carries a limit and this is unset.
PURCHASE_LIMIT_WINDOW_DAYS = env.int("PURCHASE_LIMIT_WINDOW_DAYS", default=None)

# Where the owner's alerts and daily summaries go (G38). A `.test` address here; prod.py has no
# default, so production fails to start until the owner's monitored inbox is set.
OWNER_ALERT_EMAIL = env.str("OWNER_ALERT_EMAIL", default="owner@cupnoobles.test")

# The public URL, used in mock URLs, emails and `back_urls` (§4.7), and the folder that holds the
# mock providers' state (§4.3). Tests point the folder at a per-test directory.
SITE_URL = env.str("SITE_URL", default="http://localhost:8080")
MOCK_STORE_DIR = env.str("MOCK_STORE_DIR", default=str(BASE_DIR / "var" / "mocks"))

# Signs the mock provider's notifications (9.9); `WEBHOOK_MAX_AGE_SECONDS` is the signature
# timestamp tolerance (9.A). The secret is a development value: production runs a real provider.
MOCK_PAYMENT_WEBHOOK_SECRET = env.str(
    "MOCK_PAYMENT_WEBHOOK_SECRET", default="dev-mock-payment-webhook-secret"
)
WEBHOOK_MAX_AGE_SECONDS = env.int("WEBHOOK_MAX_AGE_SECONDS", default=300)

# Gates the simulator, the mock tracking page, `/dev/test/` and the dev commands.
DEV_TOOLS_ENABLED = env.bool("DEV_TOOLS_ENABLED", default=False)

DEBUG = False

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "apps.core",
    "apps.accounts",
    "apps.catalog",
    "apps.shipping",
    "apps.inventory",
    "apps.carts",
    "apps.orders",
    "apps.payments",
    "apps.invoicing",
    "apps.notifications",
]

# Rate limits (django-ratelimit, T6.7b). The counters live in process memory: there is no Redis or
# memcached by design (ADR-0006). That is exact for one api process and loosens with each extra
# worker, so the production topology must account for it (G43). The library's check flags the
# local-memory backend as unshared; it is silenced here, knowingly.
CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}
SILENCED_SYSTEM_CHECKS = ["django_ratelimit.E003"]
RATELIMIT_IP_META_KEY = "apps.core.ratelimit.client_ip"

# Set before the first migration; changing it later is very painful (T2.1a).
AUTH_USER_MODEL = "accounts.Customer"

# One origin: the storefront and the API share cookies. Staff sessions in R1,
# customer sessions from T6.1. Nuxt reads `csrftoken` and sends `X-CSRFToken`,
# so the CSRF cookie must stay readable by script (T6.2).
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Argon2 first: new passwords use it, older hashes still verify (absorbs plan 1.4).
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-mx"  # A3
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# MEDIA_STORAGE=local: plain files under var/media/ (§4.3). The S3 backend arrives in Phase 18.
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "var" / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# OpenAPI (§4.6). The harness needs a generator; T1.13b mounts the bare schema endpoint; T5.5 tags each operation by its API area.
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Cup Noobles API",
    "VERSION": "1.0.0",
    "OAS_VERSION": "3.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/",
}
