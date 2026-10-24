"""The custom user model is wired in before the first migration (T2.1a)."""

import pytest
from django.contrib.auth import get_user_model

from tests.factories.accounts import CustomerFactory

pytestmark = pytest.mark.django_db


def test_auth_user_model_is_customer():
    assert get_user_model()._meta.label == "accounts.Customer"


def test_create_superuser_signs_in_by_email_case_insensitively():
    user = get_user_model().objects.create_superuser(
        "Staff@Example.com", "una-clave-larga-1"
    )
    assert user.is_staff and user.is_superuser and user.has_perm("catalog.add_product")
    assert get_user_model().objects.get(email="staff@example.com") == user


def test_regular_customer_holds_no_admin_permissions():
    customer = CustomerFactory()
    assert not customer.is_staff
    assert not customer.has_perm("catalog.add_product")
