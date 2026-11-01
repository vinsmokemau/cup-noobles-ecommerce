"""T11.6: the vendoring script copies the pinned DS email HTML byte for byte."""

import hashlib
import json

import pytest
import vendor_ds_email as vendor


def _installed(tmp_path, version="1.1.0"):
    installed = tmp_path / "node_modules" / "email"
    (installed / "dist").mkdir(parents=True)
    (installed / "package.json").write_text(json.dumps({"version": version}))
    (installed / "dist" / "reference.html").write_bytes(b"<p>{{ heading }}</p>\r\n")
    (installed / "dist" / "rows.html").write_bytes(b"<tr>{{ item_name }}</tr>\n")
    (installed / "dist" / "notes.txt").write_text("not html")
    return installed


def test_copies_files_and_records_version_and_sha256(tmp_path):
    target = tmp_path / "ds"
    (target).mkdir()
    (target / "stale.html").write_text("old")

    manifest = vendor.vendor(_installed(tmp_path), target, "1.1.0")

    assert sorted(p.name for p in target.iterdir()) == [
        "ds-email-manifest.json", "reference.html", "rows.html",
    ]  # fmt: skip
    assert (target / "reference.html").read_bytes() == b"<p>{{ heading }}</p>\r\n"
    assert manifest["version"] == "1.1.0"
    assert (
        manifest["files"]["rows.html"]
        == hashlib.sha256(b"<tr>{{ item_name }}</tr>\n").hexdigest()
    )
    assert json.loads((target / "ds-email-manifest.json").read_text()) == manifest


def test_refuses_an_installed_version_that_is_not_the_pin(tmp_path):
    with pytest.raises(SystemExit, match="pins 1.2.0"):
        vendor.vendor(_installed(tmp_path, "1.1.0"), tmp_path / "ds", "1.2.0")
    assert not (tmp_path / "ds").exists()
