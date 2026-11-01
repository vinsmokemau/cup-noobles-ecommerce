"""es-MX display formats for emails (DS:formatting.md, CR-30, CR-31).

The storefront formats with `Intl`; the API has no `Intl`, so these two helpers produce the same
text: `$1,234.50` with no suffix, and a long date with an explicit store timezone.
"""

from datetime import datetime

from django.utils import formats, timezone, translation

from apps.orders.numbering import STORE_TIMEZONE


def format_mxn(cents: int) -> str:
    """Integer centavos as `$1,234.50`. Integer arithmetic only (CR-01)."""
    sign = "-" if cents < 0 else ""
    pesos, centavos = divmod(abs(cents), 100)
    return f"{sign}${pesos:,}.{centavos:02d}"


def format_deadline(value: datetime) -> str:
    """A moment someone must act on: the long date and the time, in the store timezone (G5)."""
    local = timezone.localtime(value, STORE_TIMEZONE)
    with translation.override("es-mx"):
        text = formats.date_format(local, r"j \d\e F \d\e Y \a \l\a\s g:i a")
    # Django capitalizes the month; Spanish writes it in lowercase.
    return text.lower()
