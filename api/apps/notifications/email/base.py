"""Email interface (SPEC.md §4.3)."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Attachment:
    filename: str
    content_type: str
    content: bytes


@dataclass(frozen=True)
class OutgoingEmail:
    to: str
    subject: str
    html: str
    text: str
    template: str
    reply_to: str | None = None
    attachments: tuple[Attachment, ...] = ()  # the CFDI PDF and XML (REQ-060)


class EmailSendError(Exception):
    """Raised by a sender that could not hand the message to its provider."""


class EmailSender(Protocol):
    def send(self, message: OutgoingEmail) -> str:
        """Send the message; return the provider message id. Raises EmailSendError."""
        ...
