"""Renders an email's HTML on the vendored DS reference layout (SPEC.md §4.5, T11.3).

The layout file is read as the DS compiled it and is never edited. The DS asks the sending project
to repeat the `<tr>` of one item and the `<tr>` of one total with its own template language
(DS:email-components.md, rows), so `_layout_source()` wraps those two rows in `{% for %}` loops
when it loads the file. Every other slot stays a plain `{{ slot }}`, escaped by Django: no value is
marked safe.
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from django.template import Context, Engine

from apps.notifications.content import EmailContent, build_content
from apps.orders.models import Order

LAYOUT = Path(__file__).parent / "templates" / "email" / "ds" / "reference.html"

_ROW = r"<tr>(?:(?!</?tr).)*?\{\{ %s \}\}.*?</tr>"
_ITEM_SLOTS = {
    "item_name": "name",
    "item_quantity": "quantity",
    "item_amount": "amount",
}
_TOTAL_SLOTS = {"total_label": "label", "total_amount": "amount"}


def _repeat(
    source: str, first_slot: str, loop: str, slots: dict[str, str], var: str
) -> str:
    rows = re.findall(_ROW % first_slot, source, flags=re.DOTALL)
    if len(rows) != 1:
        raise RuntimeError(
            f"The DS layout must hold exactly one row with {{{{ {first_slot} }}}}, found {len(rows)}"
        )
    row = rows[0]
    body = row
    for slot, attribute in slots.items():
        body = body.replace(f"{{{{ {slot} }}}}", f"{{{{ {var}.{attribute} }}}}")
    return source.replace(row, f"{{% for {var} in {loop} %}}{body}{{% endfor %}}")


@lru_cache(maxsize=1)
def _layout_source() -> str:
    source = LAYOUT.read_text(encoding="utf-8")
    source = _repeat(source, "item_name", "items", _ITEM_SLOTS, "item")
    return _repeat(source, "total_label", "totals", _TOTAL_SLOTS, "total")


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    html: str
    text: str
    content: EmailContent


def render_html(content: EmailContent) -> str:
    """The reference layout filled with `content`'s slots, items and totals."""
    template = Engine.get_default().from_string(_layout_source())
    return template.render(
        Context({**content.slots, "items": content.items, "totals": content.totals})
    )


def render_text(content: EmailContent) -> str:
    """The plain-text counterpart of the reference layout (DS:email-layouts.md).

    Eight blocks in the order of the parts, a blank line between blocks, from the same slot values
    as the HTML. Values go in as they are: plain text has nothing to escape.
    """
    slots = content.slots
    rows = [f"{i.name}  {i.quantity}  {i.amount}" for i in content.items]
    rows += [f"{t.label}: {t.amount}" for t in content.totals]
    blocks = [
        f"{slots['logo_alt']}: {slots['home_url']}",
        f"{slots['heading']}\n\n{slots['body']}",
        f"{slots['card_title']}\n{slots['card_body']}",
        "\n".join(rows),
        slots["card_footer"],
        f"{slots['button_label']}: {slots['button_url']}",
        "---",
        f"{slots['footer_text']}\n"
        f"{slots['footer_link_label']}: {slots['footer_link_url']}",
    ]
    return "\n\n".join(block for block in blocks if block) + "\n"


def render_email(
    template: str, context: dict[str, object], order: Order | None = None
) -> RenderedEmail:
    """Build `template` from the outbox `context` and its `order`, and render its HTML and text."""
    content = build_content(template, dict(context), order)
    return RenderedEmail(
        content.subject, render_html(content), render_text(content), content
    )
