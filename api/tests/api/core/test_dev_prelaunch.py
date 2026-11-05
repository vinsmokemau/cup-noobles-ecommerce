"""T12.15: the dev-only toggle `POST /dev/test/prelaunch/` (404 where dev tools are off)."""

import importlib

import pytest
from django.urls import clear_url_caches

from apps.core.models import SiteSetting

URL = "/dev/test/prelaunch/"


@pytest.mark.django_db
def test_toggle_turns_the_mode_on_and_off(client):
    on = client.post(URL, {"on": True}, content_type="application/json")
    assert on.status_code == 200
    assert on.json() == {"prelaunch": True}
    assert SiteSetting.prelaunch_active()

    off = client.post(URL, {"on": False}, content_type="application/json")
    assert off.json() == {"prelaunch": False}
    assert not SiteSetting.prelaunch_active()


@pytest.mark.parametrize("payload", [{}, {"on": "yes"}, [True]])
@pytest.mark.django_db
def test_toggle_rejects_a_body_without_a_boolean(client, payload):
    response = client.post(URL, payload, content_type="application/json")
    assert response.status_code == 400


def test_toggle_is_post_only(client):
    assert client.get(URL).status_code == 405


def test_route_is_not_registered_when_dev_tools_are_off(client, settings):
    import config.urls

    settings.DEV_TOOLS_ENABLED = False
    clear_url_caches()
    importlib.reload(config.urls)
    try:
        response = client.post(URL, {"on": True}, content_type="application/json")
    finally:
        settings.DEV_TOOLS_ENABLED = True
        clear_url_caches()
        importlib.reload(config.urls)

    assert response.status_code == 404
