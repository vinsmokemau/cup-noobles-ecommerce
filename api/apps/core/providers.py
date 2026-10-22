"""The single place implementations are chosen (SPEC.md §4.3).

Domain code calls these functions and depends on the Protocols, never on an
implementation (CR-18). An unknown switch value is a startup error (CR-21).
"""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import default_storage
from django.utils.module_loading import import_string

if TYPE_CHECKING:
    from apps.core.errors.base import ErrorReporter
    from apps.core.media import MediaStore
    from apps.invoicing.base import InvoiceProvider
    from apps.notifications.email.base import EmailSender
    from apps.payments.base import PaymentProvider
    from apps.shipping.carriers.base import CarrierProvider
    from apps.shipping.postal import PostalCodeLookup

PAYMENT_IMPLS = {
    "mock": "apps.payments.mock.MockPaymentProvider",
    "mercadopago": "apps.payments.mercadopago.MercadoPagoProvider",
}
CARRIER_IMPLS = {
    "mock": "apps.shipping.carriers.mock.MockCarrier",
    "manual": "apps.shipping.carriers.manual.ManualCarrier",
}
EMAIL_IMPLS = {
    "file": "apps.notifications.email.file.FileEmailSender",
    "resend": "apps.notifications.email.resend.ResendEmailSender",
    "ses": "apps.notifications.email.ses.SesEmailSender",
}
ERROR_IMPLS = {
    "off": "apps.core.errors.null.NullErrorReporter",
    "sentry": "apps.core.errors.sentry.SentryErrorReporter",
}
INVOICE_IMPLS = {
    "manual": "apps.invoicing.manual.ManualInvoicer",
}


@cache
def payment_provider() -> PaymentProvider:
    return _load("PAYMENT_PROVIDER", PAYMENT_IMPLS)


@cache
def carrier() -> CarrierProvider:
    return _load("CARRIER_PROVIDER", CARRIER_IMPLS)


@cache
def email_sender() -> EmailSender:
    return _load("EMAIL_PROVIDER", EMAIL_IMPLS)


@cache
def error_reporter() -> ErrorReporter:
    return _load("ERROR_TRACKING", ERROR_IMPLS)


@cache
def invoicer() -> InvoiceProvider:
    return _load("INVOICE_PROVIDER", INVOICE_IMPLS)


def postal_code_lookup() -> PostalCodeLookup:
    from apps.shipping.postal import DbPostalCodeLookup

    return DbPostalCodeLookup()


def media_store() -> MediaStore:
    return default_storage


def clear_provider_caches() -> None:
    """Forget every chosen implementation; the next call reads the settings again."""
    for factory in (payment_provider, carrier, email_sender, error_reporter, invoicer):
        factory.cache_clear()


def _load(setting: str, impls: dict[str, str]) -> Any:
    value = getattr(settings, setting)
    if value not in impls:
        raise ImproperlyConfigured(
            f"{setting}={value!r}; expected one of {sorted(impls)}"
        )
    return import_string(impls[value])()
