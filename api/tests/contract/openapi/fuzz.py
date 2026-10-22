"""In-process schemathesis runner for the live OpenAPI schema (SPEC.md §4.6)."""

from collections.abc import Callable

import schemathesis
import yaml
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
    schema = schemathesis.openapi.from_dict(yaml.safe_load(schema_text))
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
