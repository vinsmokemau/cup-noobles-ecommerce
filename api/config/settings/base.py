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
RESERVATION_TTL_SPEI_HOURS = env.int("RESERVATION_TTL_SPEI_HOURS", default=4)
RESERVATION_TTL_OXXO_HOURS = env.int("RESERVATION_TTL_OXXO_HOURS", default=72)
PAYMENT_INSTALLMENT_OPTIONS = env.list(
    "PAYMENT_INSTALLMENT_OPTIONS", cast=int, default=[3, 6]
)

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

# Set before the first migration; changing it later is very painful (T2.1a).
AUTH_USER_MODEL = "accounts.Customer"

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

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# OpenAPI (§4.6). The harness needs a generator; T1.13b mounts the bare schema endpoint; T5.5 adds tags.
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Cup Noobles API",
    "VERSION": "1.0.0",
    "OAS_VERSION": "3.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/",
}
