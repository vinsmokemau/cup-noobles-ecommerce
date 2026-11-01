import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

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
