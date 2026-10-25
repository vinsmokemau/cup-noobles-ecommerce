"""Load `mx_postal_code` from a file (SPEC.md §4.3, T6.6, G30).

`POSTAL_CODE_DATASET=sample` loads the committed sample when no path is given; `sepomex` needs the
path of a file downloaded by hand. Never makes a network call. Idempotent: a re-run updates rows in
place. The file is a CSV with the columns `postal_code,neighborhood,municipality,state_code`; lines
starting with `#` are comments. Everything is loaded or nothing is.
"""

import csv
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.shipping.models import MxState

COLUMNS = ["postal_code", "neighborhood", "municipality", "state_code"]
SAMPLE_PATH = Path(settings.BASE_DIR) / "fixtures" / "mx_postal_codes_sample.csv"
UPSERT = """
    INSERT INTO mx_postal_code (postal_code, neighborhood, municipality, state_code)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (postal_code, neighborhood)
    DO UPDATE SET municipality = EXCLUDED.municipality, state_code = EXCLUDED.state_code
"""


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        lines = (line for line in handle if not line.startswith("#"))
        reader = csv.DictReader(lines)
        if reader.fieldnames != COLUMNS:
            raise CommandError(f"{path}: expected the columns {','.join(COLUMNS)}")
        return list(reader)


class Command(BaseCommand):
    help = "Load postal codes into mx_postal_code from a CSV file (no network)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "path",
            nargs="?",
            help="CSV file; optional only for POSTAL_CODE_DATASET=sample",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dataset = settings.POSTAL_CODE_DATASET
        if dataset not in ("sample", "sepomex"):
            raise CommandError(
                f"POSTAL_CODE_DATASET={dataset!r}; expected sample or sepomex"
            )
        if options["path"]:
            path = Path(options["path"])
        elif dataset == "sample":
            path = SAMPLE_PATH
        else:
            raise CommandError("POSTAL_CODE_DATASET=sepomex needs the path of the file")
        if not path.is_file():
            raise CommandError(f"{path}: no such file")

        rows = read_rows(path)
        known_states = set(MxState.objects.values_list("code", flat=True))
        for number, row in enumerate(rows, start=1):
            if not (
                len(row["postal_code"]) == 5
                and row["postal_code"].isdigit()
                and row["neighborhood"]
                and row["municipality"]
            ):
                raise CommandError(f"{path}, row {number}: incomplete or malformed row")
            if row["state_code"] not in known_states:
                raise CommandError(
                    f"{path}, row {number}: unknown state_code {row['state_code']!r} "
                    "(run seed_states first)"
                )

        # Raw SQL on purpose: Django 5.2's multi-row `bulk_create` mangles the `state_code`
        # foreign key of this composite-key model (`CMX` is stored as `C`).
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.executemany(
                UPSERT, [tuple(row[column] for column in COLUMNS) for row in rows]
            )
        self.stdout.write(f"load_postal_codes: {len(rows)} rows from {path.name}")
