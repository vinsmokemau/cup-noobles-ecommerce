"""Launch product types, D14 stand-in (SPEC.md §2.5, T2.8).

Each `attribute_schema` carries `"$comment": "[PLACEHOLDER]"` until D14 is decided; `check_placeholders`
(T2.9) fails while the marker remains. The attributes are the examples in the `spec/schema.sql` comments.
A type with no example (`board_game`, `accessory`) gets an empty schema.

The seed creates missing types and leaves existing rows alone, so running it again changes nothing
and edits made in the admin survive.
"""

from typing import Any

from apps.catalog.models import ProductType

PLACEHOLDER_COMMENT = "[PLACEHOLDER]"


def _schema(
    properties: dict[str, Any] | None = None, required: list[str] | None = None
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "$comment": PLACEHOLDER_COMMENT,
        "type": "object",
        "properties": properties or {},
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


LAUNCH_PRODUCT_TYPES: tuple[dict[str, Any], ...] = (
    {
        "code": "tcg_sealed",
        "name": "TCG sellado",
        "attribute_schema": _schema(
            {
                "juego": {"type": "string"},
                "set": {"type": "string"},
                "idioma": {"type": "string"},
                "sobres_por_caja": {"type": "integer"},
            },
            required=["juego"],
        ),
        "variant_axes": [],
    },
    {
        "code": "board_game",
        "name": "Juego de mesa",
        "attribute_schema": _schema(),
        "variant_axes": [],
    },
    {
        "code": "apparel",
        "name": "Ropa",
        "attribute_schema": _schema(
            {
                "material": {"type": "string"},
                "corte": {"type": "string"},
            },
            required=["material"],
        ),
        "variant_axes": ["talla", "color"],
    },
    {
        "code": "figure",
        "name": "Figura",
        "attribute_schema": _schema(
            {
                "linea": {"type": "string"},
                "numero": {"type": "integer"},
                "escala": {"type": "string"},
                "altura_mm": {"type": "integer"},
                "fabricante": {"type": "string"},
            },
            required=["linea"],
        ),
        "variant_axes": [],
    },
    {
        "code": "accessory",
        "name": "Accesorio",
        "attribute_schema": _schema(),
        "variant_axes": [],
    },
)


def seed_product_types() -> None:
    for position, spec in enumerate(LAUNCH_PRODUCT_TYPES):
        ProductType.objects.get_or_create(
            code=spec["code"],
            defaults={
                "name": spec["name"],
                "attribute_schema": spec["attribute_schema"],
                "variant_axes": spec["variant_axes"],
                "position": position,
            },
        )
