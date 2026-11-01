import re

from tests.integration.notifications.conftest import EMAIL_TEMPLATES

# Visual literals of an email: colors, font families and sizes. The DS owns every one (CR-46).
LITERAL = re.compile(
    r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)|font-family\s*:[^;\"'}]+|\b\d+(?:\.\d+)?(?:px|rem|em)\b"
)


def _literals(html: str) -> set[str]:
    return {" ".join(match.split()) for match in LITERAL.findall(html)}


def test_p11_v12_templates_built_from_vendored_ds_html(vendored_ds_email):
    vendored = vendored_ds_email.files()

    assert "reference.html" in vendored
    assert set(vendored) == set(vendored_ds_email.manifest["files"])
    for name, content in vendored.items():
        assert (
            vendored_ds_email.sha256(content)
            == vendored_ds_email.manifest["files"][name]
        ), name
    assert vendored_ds_email.manifest["version"] == vendored_ds_email.pinned_version

    # A template adds no color, font family or size of its own. (R1 templates arrive with T11.3;
    # until then the loop has nothing to read.)
    allowed = set().union(*(_literals(c.decode("utf-8")) for c in vendored.values()))
    for template in sorted(EMAIL_TEMPLATES.glob("*.html")):
        extra = _literals(template.read_text(encoding="utf-8")) - allowed
        assert not extra, f"{template.name}: {sorted(extra)}"
