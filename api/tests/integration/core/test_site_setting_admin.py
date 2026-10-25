"""T5.7: staff turn pre-launch mode on and off in the admin (G32, ADR-0038)."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import Customer
from apps.core.models import SiteSetting

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client():
    owner = Customer.objects.create_superuser(
        email="owner@cupnoobles.test", password="x"
    )
    client = Client()
    client.force_login(owner)
    return client


def test_site_setting_defaults_to_off():
    assert SiteSetting.prelaunch_active() is False
    assert SiteSetting.objects.create().prelaunch_mode is False


def test_staff_turn_the_mode_on_and_off(admin_client):
    add = reverse("admin:core_sitesetting_add")
    assert admin_client.post(add, {"prelaunch_mode": "on"}).status_code == 302
    assert SiteSetting.prelaunch_active() is True

    change = reverse("admin:core_sitesetting_change", args=[1])
    assert admin_client.post(change, {}).status_code == 302
    assert SiteSetting.prelaunch_active() is False


def test_only_one_row_and_no_delete(admin_client):
    SiteSetting.objects.create()

    assert admin_client.get(reverse("admin:core_sitesetting_add")).status_code == 403
    delete = reverse("admin:core_sitesetting_delete", args=[1])
    assert admin_client.post(delete, {"post": "yes"}).status_code == 403
    assert SiteSetting.objects.count() == 1
