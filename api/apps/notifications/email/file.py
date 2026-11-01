"""Part A email sender: writes each message to disk (SPEC.md §4.3)."""

import secrets
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from apps.notifications.email.base import EmailSendError, OutgoingEmail


class FileEmailSender:
    """Writes `<ts>-<template>-<outbox id>.html`, a matching `.txt`, and each attachment as
    `<same prefix>-<filename>`, under `EMAIL_FILE_DIR`. With `EMAIL_MOCK_FAIL` set, every send
    raises `EmailSendError` and writes nothing."""

    def send(self, message: OutgoingEmail) -> str:
        if settings.EMAIL_MOCK_FAIL:
            raise EmailSendError("EMAIL_MOCK_FAIL is set")
        stamp = timezone.now().strftime("%Y%m%d-%H%M%S")
        tail = (
            str(message.outbox_id)
            if message.outbox_id is not None
            else secrets.token_hex(4)
        )
        prefix = f"{stamp}-{message.template}-{tail}"
        folder = Path(settings.EMAIL_FILE_DIR)
        try:
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{prefix}.html").write_text(message.html, encoding="utf-8")
            (folder / f"{prefix}.txt").write_text(message.text, encoding="utf-8")
            for attachment in message.attachments:
                name = Path(attachment.filename).name
                (folder / f"{prefix}-{name}").write_bytes(attachment.content)
        except OSError as error:
            raise EmailSendError(str(error)) from error
        return prefix
