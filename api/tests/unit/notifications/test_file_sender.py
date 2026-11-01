import re
from pathlib import Path

import pytest
from django.conf import settings as django_settings

from apps.core import providers
from apps.notifications.email.base import Attachment, EmailSendError, OutgoingEmail
from apps.notifications.email.file import FileEmailSender


def _message(**overrides) -> OutgoingEmail:
    fields = {
        "to": "cliente@example.test",
        "subject": "Tu pedido",
        "html": "<p>Hola</p>",
        "text": "Hola",
        "template": "order_confirmation",
        "reply_to": django_settings.EMAIL_REPLY_TO,
    }
    return OutgoingEmail(**{**fields, **overrides})


def _names(settings) -> list[str]:

    return sorted(p.name for p in Path(settings.EMAIL_FILE_DIR).iterdir())


def test_p11_v08_file_names_and_reply_to(settings):
    message = _message(outbox_id=42)

    FileEmailSender().send(message)

    pattern = r"\d{8}-\d{6}-order_confirmation-42\.(html|txt)"
    names = _names(settings)
    assert len(names) == 2
    assert all(re.fullmatch(pattern, n) for n in names)
    assert {n.rsplit(".", 1)[1] for n in names} == {"html", "txt"}
    assert message.reply_to == settings.EMAIL_REPLY_TO

    FileEmailSender().send(_message(outbox_id=None))

    tokens = {
        m.group(1)
        for n in _names(settings)
        if (m := re.fullmatch(r"\d{8}-\d{6}-order_confirmation-(\w+)\.html", n))
    }
    random_token = tokens - {"42"}
    assert len(random_token) == 1
    assert re.fullmatch(r"[0-9a-f]{8}", random_token.pop())


def test_file_sender_writes_bodies_and_attachments_next_to_the_html(settings):

    attachments = (
        Attachment("factura.pdf", "application/pdf", b"%PDF-1"),
        Attachment("factura.xml", "application/xml", b"<cfdi/>"),
    )

    prefix = FileEmailSender().send(
        _message(outbox_id=7, attachments=attachments, html="<p>ñ</p>", text="ñ")
    )

    folder = Path(settings.EMAIL_FILE_DIR)
    assert (folder / f"{prefix}.html").read_text(encoding="utf-8") == "<p>ñ</p>"
    assert (folder / f"{prefix}.txt").read_text(encoding="utf-8") == "ñ"
    assert (folder / f"{prefix}-factura.pdf").read_bytes() == b"%PDF-1"
    assert (folder / f"{prefix}-factura.xml").read_bytes() == b"<cfdi/>"


def test_mock_fail_raises_and_writes_nothing(settings):
    settings.EMAIL_MOCK_FAIL = True

    with pytest.raises(EmailSendError):
        FileEmailSender().send(_message(outbox_id=1))

    from pathlib import Path

    assert not Path(settings.EMAIL_FILE_DIR).exists()


def test_provider_registry_returns_the_file_sender():
    providers.clear_provider_caches()
    assert isinstance(providers.email_sender(), FileEmailSender)
