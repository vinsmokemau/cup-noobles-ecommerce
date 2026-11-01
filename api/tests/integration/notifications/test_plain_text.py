from html.parser import HTMLParser

import pytest

from apps.notifications.rendering import render_email
from tests.integration.notifications.conftest import R1_TEMPLATES

pytestmark = pytest.mark.django_db


class HtmlTokens(HTMLParser):
    """The texts and link addresses of an HTML email, in document order.

    A link yields its label and then its address; an image yields its alt text; the address of an
    image (`src`) is not text. Styles, the title and comments carry no content.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tokens: list[str] = []
        self._skip = 0
        self._href: str | None = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in ("style", "title", "head"):
            self._skip += 1
        elif tag == "img" and attributes.get("alt"):
            self.tokens.append(attributes["alt"].strip())
        elif tag == "a" and attributes.get("href"):
            self._href = attributes["href"].strip()

    def handle_endtag(self, tag):
        if tag in ("style", "title", "head"):
            self._skip -= 1
        elif tag == "a" and self._href is not None:
            self.tokens.append(self._href)
            self._href = None

    def handle_data(self, data):
        text = " ".join(data.split())
        if text and not self._skip:
            self.tokens.append(text)


def html_tokens(html: str) -> list[str]:
    parser = HtmlTokens()
    parser.feed(html)
    return parser.tokens


@pytest.mark.parametrize("template", R1_TEMPLATES)
def test_p11_v13_text_part_complete(template, template_context):
    context, order = template_context(template)

    email = render_email(template, context, order)

    # The text part is flat: each token of the HTML must appear in it, each after the previous one.
    position = 0
    for token in html_tokens(email.html):
        found = email.text.find(token, position)
        assert found != -1, f"{token!r} is missing, or out of order, in the text part"
        position = found + len(token)


@pytest.mark.parametrize("template", R1_TEMPLATES)
def test_p11_v13_text_part_is_plain(template, template_context):
    context, order = template_context(template)

    text = render_email(template, context, order).text

    assert "<" not in text and "&amp;" not in text and "{{" not in text
    assert not any(line != line.rstrip() for line in text.splitlines())
    assert "\n\n\n" not in text
    assert "logo-horizontal.png" not in text  # the address of the logo is not text


def test_p11_v13_text_part_follows_the_dss_blocks(template_context):
    context, order = template_context("order_confirmation")

    email = render_email("order_confirmation", context, order)
    slots = email.content.slots

    assert email.text == (
        f"Cup Noobles: {slots['home_url']}\n\n"
        f"{slots['heading']}\n\n{slots['body']}\n\n"
        f"{slots['card_title']}\n{slots['card_body']}\n\n"
        "Caja de sobres & más (Español)  x2  $200.00\n"
        "Dados  x1  $50.00\n"
        "Subtotal: $250.00\nEnvío: $99.00\nTotal: $349.00\n\n"
        f"{slots['card_footer']}\n\n"
        f"{slots['button_label']}: {slots['button_url']}\n\n"
        "---\n\n"
        f"{slots['footer_text']}\n"
        f"{slots['footer_link_label']}: {slots['footer_link_url']}\n"
    )
