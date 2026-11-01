#!/usr/bin/env python3
"""Vendor the Design System email HTML into the API (SPEC.md §4.5, T11.6).

Copies `dist/*.html` of the `@vinsmokemau/cup-noobles-email` package installed in `web/node_modules`
into `api/apps/notifications/templates/email/ds/` and writes `ds-email-manifest.json` there, with
the DS version and the sha256 of each file. Run it from the host after `pnpm install`, and again in
any task that raises the DS pin. The vendored files are never edited by hand.

Fails (exit 1) when the installed package is not the version pinned in `web/package.json`.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = "@vinsmokemau/cup-noobles-email"
INSTALLED = ROOT / "web" / "node_modules" / PACKAGE
TARGET = ROOT / "api" / "apps" / "notifications" / "templates" / "email" / "ds"
MANIFEST = "ds-email-manifest.json"


def pinned_version(root: Path = ROOT) -> str:
    package = json.loads((root / "web" / "package.json").read_text(encoding="utf-8"))
    for section in ("dependencies", "devDependencies"):
        if PACKAGE in package.get(section, {}):
            return package[section][PACKAGE]
    raise SystemExit(f"{PACKAGE} is not in web/package.json")


def vendor(installed: Path, target: Path, pinned: str) -> dict:
    version = json.loads((installed / "package.json").read_text(encoding="utf-8"))[
        "version"
    ]
    if version != pinned:
        raise SystemExit(
            f"web/node_modules has {PACKAGE} {version}, web/package.json pins {pinned}: "
            "run `pnpm install` in web/ first"
        )
    sources = sorted((installed / "dist").glob("*.html"))
    if not sources:
        raise SystemExit(f"no dist/*.html in {installed}")

    target.mkdir(parents=True, exist_ok=True)
    for stale in target.glob("*.html"):
        stale.unlink()
    files = {}
    for source in sources:
        content = source.read_bytes()
        (target / source.name).write_bytes(content)
        files[source.name] = hashlib.sha256(content).hexdigest()

    manifest = {"package": PACKAGE, "version": version, "files": files}
    (target / MANIFEST).write_bytes(
        (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    )
    return manifest


def main() -> int:
    manifest = vendor(INSTALLED, TARGET, pinned_version())
    print(f"vendored {len(manifest['files'])} files of {PACKAGE} {manifest['version']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
