"""Form fields for `product.attributes`, one per `attribute_schema` property (SPEC.md §4.4, T3.4).

`string` is a text box, `string` with `enum` a select, `integer` and `number` a number box and
`boolean` a checkbox. A property of any other shape gets its own JSON textarea. A schema this module
cannot read at all, or attributes that do not fit it, yield `None`: the admin then shows the raw
`attributes` JSON field instead, never an error page.
"""

from typing import Any

from django import forms

FIELD_PREFIX = "attr_"


def field_name(key: str) -> str:
    return f"{FIELD_PREFIX}{key}"


def _field_for(
    key: str, spec: Any, required: bool, initial: Any, has_initial: bool
) -> forms.Field:
    options: dict[str, Any] = {
        "required": required,
        "label": spec.get("title", key) if isinstance(spec, dict) else key,
        "help_text": spec.get("description", "") if isinstance(spec, dict) else "",
    }
    if has_initial:
        options["initial"] = initial
    kind = spec.get("type") if isinstance(spec, dict) else None
    if kind == "string" and isinstance(spec.get("enum"), list):
        choices = [(value, str(value)) for value in spec["enum"]]
        if not required:
            choices.insert(0, ("", "---------"))
        return forms.ChoiceField(choices=choices, **options)
    if kind == "string":
        return forms.CharField(**options)
    if kind == "integer":
        return forms.IntegerField(**options)
    if kind == "number":
        return forms.FloatField(**options)
    if kind == "boolean":
        # An unchecked box is a real answer, so a boolean is never "missing".
        return forms.BooleanField(**{**options, "required": False})
    return forms.JSONField(**options)


def build_attribute_fields(schema: Any, current: Any) -> dict[str, forms.Field] | None:
    """Map `attr_<key>` to a form field for every schema property, or `None` to use the JSON fallback."""
    if not isinstance(schema, dict) or not isinstance(schema.get("properties"), dict):
        return None
    properties: dict[str, Any] = schema["properties"]
    current = current if isinstance(current, dict) else {}
    if any(key not in properties for key in current):
        return None
    required = schema.get("required")
    required_keys = set(required) if isinstance(required, list) else set()
    return {
        field_name(key): _field_for(
            key, spec, key in required_keys, current.get(key), key in current
        )
        for key, spec in properties.items()
    }


def collect_attributes(
    cleaned_data: dict[str, Any], fields: dict[str, forms.Field]
) -> dict[str, Any]:
    """Rebuild the `attributes` dict from the cleaned form values, leaving out empty optional ones."""
    attributes: dict[str, Any] = {}
    for name, field in fields.items():
        if name not in cleaned_data:
            continue
        value = cleaned_data[name]
        if isinstance(field, forms.BooleanField):
            attributes[name.removeprefix(FIELD_PREFIX)] = bool(value)
        elif value not in (None, ""):
            attributes[name.removeprefix(FIELD_PREFIX)] = value
    return attributes
