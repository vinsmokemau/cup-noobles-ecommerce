import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.factories.orders import STAND_IN_ADDRESS, OrderFactory, OrderLineFactory

R1_TEMPLATES = (
    "order_confirmation",
    "oxxo_voucher",
    "order_expired",
    "order_shipped",
    "order_cancelled",
    "refund_issued",
    "cfdi_issued",
)
EMAIL_TEMPLATES = (
    Path(__file__).parents[3] / "apps" / "notifications" / "templates" / "email"
)
# In the api container the repository root is mounted at /repo (docker-compose.yml).
WEB_PACKAGE_CANDIDATES = (
    Path("/repo/web/package.json"),
    Path(__file__).parents[4] / "web" / "package.json",
)


@dataclass
class VendoredDSEmail:
    directory: Path
    manifest: dict
    pinned_version: str

    def files(self) -> dict[str, bytes]:
        return {p.name: p.read_bytes() for p in sorted(self.directory.glob("*.html"))}

    @staticmethod
    def sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()


@pytest.fixture
def vendored_ds_email() -> VendoredDSEmail:
    """`ds-email-manifest.json` and the vendored DS email files, with the DS version `web/` pins."""
    directory = EMAIL_TEMPLATES / "ds"
    manifest = json.loads(
        (directory / "ds-email-manifest.json").read_text(encoding="utf-8")
    )
    package_json = next(p for p in WEB_PACKAGE_CANDIDATES if p.exists())
    dependencies = json.loads(package_json.read_text(encoding="utf-8"))["dependencies"]
    return VendoredDSEmail(
        directory, manifest, dependencies["@vinsmokemau/cup-noobles-email"]
    )


TEMPLATE_CONTEXTS = {
    "order_confirmation": {},
    "oxxo_voucher": {
        "voucher_url": "https://tienda.example.test/ficha/1/",
        "voucher_expires_at": datetime(2026, 3, 4, 18, 0, tzinfo=UTC).isoformat(),
    },
    "order_expired": {},
    "order_shipped": {
        "carrier": "manual",
        "tracking_number": "GUIA000123",
        "tracking_url": "https://paqueteria.example.test/rastreo/GUIA000123",
    },
    "order_cancelled": {"refunded_cents": 0},
    "refund_issued": {"refund_cents": 5000, "refunded_total_cents": 5000},
    "cfdi_issued": {"folio": "A-1001"},
}


@pytest.fixture
def template_context():
    """`template_context(template)` returns `(context, order)`: an order with two lines and the
    outbox context the template's trigger writes, built through factories."""

    def build(template):
        order = OrderFactory(
            state="paid",
            shipping_address=STAND_IN_ADDRESS,
            subtotal_cents=25000,
            shipping_cents=9900,
            total_cents=34900,
        )
        OrderLineFactory(
            order=order,
            product_name="Caja de sobres & más",
            quantity=2,
            unit_price_cents=10000,
            options_snapshot={"Idioma": "Español"},
        )
        OrderLineFactory(
            order=order, product_name="Dados", quantity=1, unit_price_cents=5000
        )
        context = {"order_number": order.number, **TEMPLATE_CONTEXTS[template]}
        return context, order

    return build


@dataclass
class SentEmail:
    prefix: str
    html: str
    text: str
    attachments: dict[str, bytes]


class Mailbox:
    """The emails `FileEmailSender` wrote to `EMAIL_FILE_DIR`, with their attachments."""

    def __init__(self, folder: Path):
        self.folder = folder

    def messages(self) -> list[SentEmail]:
        if not self.folder.exists():
            return []
        found = []
        for html in sorted(self.folder.glob("*.html")):
            prefix = html.stem
            attachments = {
                p.name[len(prefix) + 1 :]: p.read_bytes()
                for p in sorted(self.folder.iterdir())
                if p.name.startswith(f"{prefix}-")
            }
            found.append(
                SentEmail(
                    prefix,
                    html.read_text(encoding="utf-8"),
                    html.with_suffix(".txt").read_text(encoding="utf-8"),
                    attachments,
                )
            )
        return found


@pytest.fixture
def mailbox(settings) -> Mailbox:
    """`mailbox.messages()` parses the files in `EMAIL_FILE_DIR` into messages."""
    return Mailbox(Path(settings.EMAIL_FILE_DIR))
