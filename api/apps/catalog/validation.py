"""Validation of `product.attributes` against `product_type.attribute_schema` (SPEC.md §4.4, T2.5).

One function does the work. `Product.clean()`, `Product.save()` and the DRF serializer all call it,
so the admin, the API and any script reject the same data with the same message. Each failure
carries the JSON pointer of the offending value (`/numero`), so a form can say which field is wrong.
"""

from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaValidationError

ATTRIBUTES_FIELD = "attributes"
INVALID_CODE = "invalid_attribute"


@dataclass(frozen=True)
class AttributeIssue:
    pointer: str
    detail: str

    def __str__(self) -> str:
        return f"{self.pointer}: {self.detail}"


def _pointer(path: list[Any]) -> str:
    # RFC 6901: "~" and "/" inside a key are escaped.
    return "".join(
        f"/{str(part).replace('~', '~0').replace('/', '~1')}" for part in path
    )


def _issues_for(error: SchemaValidationError) -> list[AttributeIssue]:
    """Point at the missing or unknown key when the schema complains about the object itself."""
    path = list(error.absolute_path)
    instance = error.instance
    if error.validator == "required" and isinstance(instance, dict):
        return [
            AttributeIssue(_pointer([*path, key]), "is a required property")
            for key in error.validator_value
            if key not in instance
        ]
    if error.validator == "additionalProperties" and isinstance(instance, dict):
        schema = error.schema if isinstance(error.schema, dict) else {}
        known = set(schema.get("properties", {}))
        return [
            AttributeIssue(_pointer([*path, key]), "is not an allowed property")
            for key in instance
            if key not in known
        ]
    return [AttributeIssue(_pointer(path) or "/", error.message)]


def attribute_issues(attributes: Any, schema: dict[str, Any]) -> list[AttributeIssue]:
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(attributes),
        key=lambda e: [str(p) for p in e.absolute_path],
    )
    return [issue for error in errors for issue in _issues_for(error)]


def validate_attributes(attributes: Any, schema: dict[str, Any]) -> None:
    """Raise `ValidationError({"attributes": [...]})`, one entry per failure, each `"/pointer: detail"`."""
    issues = attribute_issues(attributes, schema)
    if issues:
        raise ValidationError(
            {
                ATTRIBUTES_FIELD: [
                    ValidationError(
                        "%(pointer)s: %(detail)s",
                        code=INVALID_CODE,
                        params={"pointer": issue.pointer, "detail": issue.detail},
                    )
                    for issue in issues
                ]
            }
        )
