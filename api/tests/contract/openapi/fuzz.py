"""In-process schemathesis runner for the live OpenAPI schema (SPEC.md §4.6)."""

from collections.abc import Callable
from typing import Any

import schemathesis
import yaml
from django.core.signals import request_finished, request_started
from django.db import close_old_connections
from hypothesis import HealthCheck, given, settings
from schemathesis.checks import (
    content_type_conformance,
    not_a_server_error,
    response_schema_conformance,
    status_code_conformance,
)

CHECKS = (
    not_a_server_error,
    status_code_conformance,
    content_type_conformance,
    response_schema_conformance,
)
# Webhooks are covered by 9.13; dev tools are not part of the public contract.
EXCLUDED_PATH_REGEX = r"^/(api/webhooks|dev)/"


def fuzz_schema(
    schema_text: str, app: Callable, *, max_examples: int, headers: dict | None = None
) -> int:
    """Fuzz every operation of the schema against the WSGI app; return how many ran.

    Raises on the first failed check. A schema with no operations passes.
    """
    # The Django test client does this too: a request must not close the test's connection.
    request_started.disconnect(close_old_connections)
    request_finished.disconnect(close_old_connections)
    try:
        return _fuzz(schema_text, app, max_examples=max_examples, headers=headers)
    finally:
        request_started.connect(close_old_connections)
        request_finished.connect(close_old_connections)


def _fuzz(
    schema_text: str, app: Callable, *, max_examples: int, headers: dict | None
) -> int:
    schema: Any = schemathesis.openapi.from_dict(yaml.safe_load(schema_text))
    schema = schema.exclude(path_regex=EXCLUDED_PATH_REGEX)
    count = 0
    for result in schema.get_all_operations():
        operation = result.ok()

        @given(case=operation.as_strategy())
        @settings(
            max_examples=max_examples,
            deadline=None,
            suppress_health_check=list(HealthCheck),
        )
        def run(case):
            response = case.call(app=app, headers=headers)
            case.validate_response(response, checks=CHECKS)

        run()
        count += 1
    return count
