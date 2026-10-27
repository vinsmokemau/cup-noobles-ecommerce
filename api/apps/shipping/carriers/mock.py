"""The mock carrier (SPEC.md §4.3, 10.9). `MOCK_STORE_DIR/carrier/` holds its state.

State lives in one JSON file per tracking number: the current status plus an event history. It sits
outside the database for the same reason as the mock payment provider (9.9). Every write is atomic
(temp file + rename).
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import quote

from django.conf import settings
from django.utils import timezone

from apps.orders.models import Order
from apps.shipping.carriers.base import ShipmentRef, ShipmentStatus


class MockCarrier:
    code = "mock"

    def create_shipment(
        self, order: Order, *, tracking_number: str | None = None
    ) -> ShipmentRef:
        """Use the number staff typed, or `MOCK-<order number>-<n>` with `n` = shipments so far + 1."""
        number = (tracking_number or "").strip()
        if not number:
            number = f"MOCK-{order.number}-{order.shipments.count() + 1}"
        self._write(
            number,
            {
                "tracking_number": number,
                "status": ShipmentStatus.IN_TRANSIT.value,
                "events": [self._event(ShipmentStatus.IN_TRANSIT)],
            },
        )
        return ShipmentRef(
            carrier=self.code,
            tracking_number=number,
            tracking_url=f"{settings.SITE_URL}/dev/carrier/track/{quote(number, safe='')}/",
        )

    def get_status(self, tracking_number: str) -> ShipmentStatus:
        """The stored status; a tracking number the store has never seen is `UNKNOWN`."""
        try:
            stored = json.loads(self._path(tracking_number).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return ShipmentStatus.UNKNOWN
        return ShipmentStatus(stored["status"])

    @staticmethod
    def _event(status: ShipmentStatus) -> dict[str, str]:
        return {"status": status.value, "at": timezone.now().isoformat()}

    @staticmethod
    def _folder() -> Path:
        return Path(settings.MOCK_STORE_DIR) / "carrier"

    def _path(self, tracking_number: str) -> Path:
        """Staff-typed numbers are escaped, so none can name a path outside the folder."""
        return self._folder() / f"{quote(tracking_number, safe='')}.json"

    def _write(self, tracking_number: str, record: dict[str, Any]) -> None:
        """Write the record atomically: a temporary file in the same folder, then a rename."""
        folder = self._folder()
        folder.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=folder, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(record, handle)
            os.replace(temp_path, self._path(tracking_number))
        except BaseException:
            os.unlink(temp_path)
            raise
