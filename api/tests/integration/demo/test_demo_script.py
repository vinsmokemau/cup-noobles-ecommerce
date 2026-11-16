"""P15-V10 (T15.7): `docs/demo-script.md` and the demo dataset agree.

The script is read the way its reader reads it. A step is a `### <n>. <title>` section; one whose
title carries `[R2]` is not a Release 1 step. Inside a step, text in backticks names the data: a
product (`[DEMO] …`), its page (`/producto/<slug>`), a SKU (`DEMO-…`), an email, and a stock
count written next to its SKU as "(on hand: <n>)".
"""

import re
from pathlib import Path

import pytest
from django.core.management import call_command
from django.db.models import Sum

from apps.accounts.models import Customer
from apps.catalog.models import Product, Variant
from apps.inventory.models import StockItem
from apps.orders.models import Order
from tests.integration.demo.test_seed_demo import row_counts, snapshot

pytestmark = pytest.mark.django_db

API_DIR = Path(__file__).resolve().parents[3]
# In the api container the repository root is mounted at /repo (docker-compose.yml).
SCRIPT_CANDIDATES = (
    Path("/repo/docs/demo-script.md"),
    API_DIR.parent / "docs" / "demo-script.md",
)

# The Release 1 steps of SPEC.md 15.B: steps 11 and 12 are Release 2.
R1_STEPS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 14]

STEP_HEADING = re.compile(r"^### (\d+)\. (.+)$", re.MULTILINE)
ANY_HEADING = re.compile(r"^#{1,3} ", re.MULTILINE)
PRODUCT_NAME = re.compile(r"`(\[DEMO\] [^`]+)`")
PRODUCT_PAGE = re.compile(r"`/producto/([a-z0-9-]+)`")
SKU = re.compile(r"`(DEMO-[A-Z0-9-]+)`")
EMAIL = re.compile(r"`([^`\s]+@[^`\s]+)`")
STATED_STOCK = re.compile(r"`(DEMO-[A-Z0-9-]+)` \(on hand: (\d+)\)")


def demo_script() -> str:
    for path in SCRIPT_CANDIDATES:
        if path.exists():
            return path.read_text(encoding="utf-8")
    raise AssertionError(f"no demo script at any of {SCRIPT_CANDIDATES}")


def r1_steps(script: str) -> dict[int, str]:
    """Step number -> the text of the step, for the steps that are not marked `[R2]`."""
    steps = {}
    for heading in STEP_HEADING.finditer(script):
        following = ANY_HEADING.search(script, heading.end())
        end = following.start() if following else len(script)
        if "[R2]" not in heading.group(2):
            steps[int(heading.group(1))] = script[heading.end() : end]
    return steps


def on_hand(sku: str) -> int:
    total = StockItem.objects.filter(variant__sku=sku).aggregate(n=Sum("on_hand"))["n"]
    return total or 0


def test_p15_v10_demo_script_matches_seed():
    steps = r1_steps(demo_script())
    assert sorted(steps) == R1_STEPS
    text = "\n".join(steps[number] for number in R1_STEPS)

    names = set(PRODUCT_NAME.findall(text))
    slugs = set(PRODUCT_PAGE.findall(text))
    skus = set(SKU.findall(text))
    emails = set(EMAIL.findall(text))
    stated = [(sku, int(units)) for sku, units in STATED_STOCK.findall(text)]
    # The script names its data; a script that named none would pass every check below.
    assert names and slugs and skus and emails
    # Every SKU the steps mention comes with its stock.
    assert {sku for sku, _ in stated} == skus

    call_command("seed_demo")

    visible = Product.objects.filter(status="active")
    assert names <= set(visible.values_list("name", flat=True))
    assert slugs <= set(visible.values_list("slug", flat=True))
    assert skus <= set(Variant.objects.values_list("sku", flat=True))
    # An email of the script is the staff user's or the one of the seeded guest orders.
    known = set(Customer.objects.values_list("email", flat=True)) | set(
        Order.objects.values_list("email", flat=True)
    )
    assert emails <= known
    for sku, units in stated:
        assert on_hand(sku) == units, sku

    # A second run produces identical data: nothing is added, changed or removed.
    seeded = (snapshot(), row_counts())
    call_command("seed_demo")
    assert (snapshot(), row_counts()) == seeded
