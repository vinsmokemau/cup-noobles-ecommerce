"""Centavos/pesos conversion (SPEC.md 9.2, §4.6 Property-based, CR-01)."""

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from apps.payments.money import cents_to_pesos, pesos_to_cents


@given(cents=st.integers(min_value=0, max_value=10**15))
def test_p9_v08_round_trip_property(cents):
    assert pesos_to_cents(cents_to_pesos(cents)) == cents


def test_p9_v08_conversion_edges():
    assert pesos_to_cents("1160.00") == 116000
    assert pesos_to_cents("1160") == 116000
    assert pesos_to_cents(Decimal("0.05")) == 5
    assert pesos_to_cents("0") == 0
    assert cents_to_pesos(116000) == Decimal("1160.00")
    assert cents_to_pesos(5) == Decimal("0.05")
    assert str(cents_to_pesos(0)) == "0.00"
    assert isinstance(pesos_to_cents("1160.00"), int)

    for sub_centavo in ("1160.009", "0.001", Decimal("1.005")):
        with pytest.raises(ValueError):
            pesos_to_cents(sub_centavo)
    for negative in ("-1.00", Decimal("-0.01")):
        with pytest.raises(ValueError):
            pesos_to_cents(negative)
    with pytest.raises(ValueError):
        cents_to_pesos(-1)
    for not_an_amount in ("", "abc", "NaN", "Infinity", "1,160.00"):
        with pytest.raises(ValueError):
            pesos_to_cents(not_an_amount)
    with pytest.raises(TypeError):
        pesos_to_cents(11.6)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        cents_to_pesos(True)
    with pytest.raises(TypeError):
        cents_to_pesos(1.5)  # type: ignore[arg-type]
