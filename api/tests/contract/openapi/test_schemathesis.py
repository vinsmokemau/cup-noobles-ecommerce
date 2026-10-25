"""Schemathesis against the live schema, plus a self-test that the runner can fail."""

import os

import pytest
from django.core.handlers.wsgi import WSGIHandler

from tests.contract.openapi.fuzz import fuzz_schema
from tests.contract.openapi.snapshot import generate_schema_text

# make test: 25 examples; make test-all (HYPOTHESIS_PROFILE=ci): 200.
MAX_EXAMPLES = 200 if os.environ.get("HYPOTHESIS_PROFILE") == "ci" else 25


@pytest.fixture
def staff_headers(client, django_user_model):
    staff = django_user_model.objects.create_user("staff", password="x", is_staff=True)
    client.force_login(staff)
    return {"Cookie": f"sessionid={client.cookies['sessionid'].value}"}


@pytest.mark.django_db
def test_live_schema_conforms_anonymously():
    fuzz_schema(generate_schema_text(), WSGIHandler(), max_examples=MAX_EXAMPLES)


@pytest.mark.django_db
def test_live_schema_conforms_as_staff(staff_headers):
    fuzz_schema(
        generate_schema_text(),
        WSGIHandler(),
        max_examples=MAX_EXAMPLES,
        headers=staff_headers,
    )


@pytest.mark.django_db
def test_runner_passes_a_conforming_endpoint(settings):
    settings.ROOT_URLCONF = "tests.contract.openapi.urls_good"
    ran = fuzz_schema(generate_schema_text(), WSGIHandler(), max_examples=5)
    assert ran == 1


@pytest.mark.django_db
def test_runner_fails_a_nonconforming_endpoint(settings):
    settings.ROOT_URLCONF = "tests.contract.openapi.urls_broken"
    with pytest.raises(BaseExceptionGroup, match="Schemathesis found"):
        fuzz_schema(generate_schema_text(), WSGIHandler(), max_examples=5)


@pytest.mark.django_db
def test_p5_v11_catalog_fuzz():
    ran = fuzz_schema(
        generate_schema_text(),
        WSGIHandler(),
        max_examples=MAX_EXAMPLES,
        path_prefix="/api/catalog/",
    )
    assert ran == 5
