"""Product slugs (SPEC.md §4.4, T3.2).

`slugify` turns a name into a URL part, `unique_slug` adds `-2`, `-3` on collision, and
`ensure_slug_unchanged` stops a published product from changing its slug: the URL is already
public and indexed. `Product.save()` calls the last two, so the admin, the services and any
script follow the same rules.
"""

from django.core.exceptions import ValidationError
from django.db.models import Model
from django.utils.text import slugify as django_slugify

# Used when a name has no letters or digits at all (for example "!!!").
FALLBACK_SLUG = "producto"
SLUG_IMMUTABLE_CODE = "slug_immutable"


def slugify(name: str) -> str:
    """ASCII, lowercase, hyphen-separated: "Pokémon Booster Box" -> "pokemon-booster-box"."""
    return django_slugify(name) or FALLBACK_SLUG


def unique_slug(model: type[Model], name: str, *, exclude_pk: int | None = None) -> str:
    """The first of `x`, `x-2`, `x-3`, … that no other row of `model` uses.

    `slug` is a `citext` column, so the comparison ignores case, like the unique index does.
    """
    base = slugify(name)
    taken = model._default_manager.exclude(pk=exclude_pk)
    candidate, suffix = base, 1
    while taken.filter(slug=candidate).exists():
        suffix += 1
        candidate = f"{base}-{suffix}"
    return candidate


def ensure_slug_unchanged(instance: Model) -> None:
    """Raise `ValidationError({"slug": …})` if the stored row is published and the slug differs."""
    if instance.pk is None:
        return
    stored = (
        type(instance)
        ._default_manager.filter(pk=instance.pk)
        .values_list("slug", "published_at")
        .first()
    )
    if stored is None:
        return
    stored_slug, published_at = stored
    if published_at is not None and instance.slug != stored_slug:  # type: ignore[attr-defined]
        raise ValidationError(
            {
                "slug": ValidationError(
                    "The slug cannot change after the product is published.",
                    code=SLUG_IMMUTABLE_CODE,
                )
            }
        )
