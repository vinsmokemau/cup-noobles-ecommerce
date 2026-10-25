import re
from datetime import UTC, datetime

import pytest

from apps.orders.numbering import next_order_number

NUMBER = re.compile(r"^CN-\d{4}-\d{6}$")


def local_midnight_utc(year: int) -> datetime:
    """1 January 00:00 in America/Mexico_City (UTC-6, no DST in winter), in UTC."""
    return datetime(year, 1, 1, 6, 0, tzinfo=UTC)


@pytest.mark.django_db
def test_p8_v12_number_format_and_year_rollover():
    # 23:59 on 31 December local time is already 1 January in UTC: the year is the local one.
    last_minute_2090 = datetime(2091, 1, 1, 5, 59, tzinfo=UTC)
    first_minute_2091 = local_midnight_utc(2091)

    first = next_order_number(last_minute_2090)
    second = next_order_number(last_minute_2090)
    rolled = next_order_number(first_minute_2091)
    rolled_again = next_order_number(first_minute_2091)

    assert all(NUMBER.match(n) for n in (first, second, rolled, rolled_again))
    assert (first, second) == ("CN-2090-000001", "CN-2090-000002")
    assert (rolled, rolled_again) == ("CN-2091-000001", "CN-2091-000002")


@pytest.mark.django_db
def test_number_defaults_to_the_current_time():
    assert NUMBER.match(next_order_number())
