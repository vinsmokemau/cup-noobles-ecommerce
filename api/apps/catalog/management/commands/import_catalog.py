"""`manage.py import_catalog <file.csv>`: idempotent catalog import keyed on SKU (SPEC.md T3.6).

The file path is given at run time. A catalog file that holds costs is never committed (CR-49).
"""

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.importer import COLUMNS, MissingColumns, import_catalog


class Command(BaseCommand):
    help = (
        "Import products and variants from a CSV, keyed on SKU. Columns: "
        + ",".join(COLUMNS)
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("file", type=Path, help="Path to the CSV file.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change and write nothing.",
        )
        parser.add_argument(
            "--images-dir",
            type=Path,
            help="Folder that the paths in image_urls are relative to (no network access).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        path: Path = options["file"]
        images_dir: Path | None = options["images_dir"]
        if not path.is_file():
            raise CommandError(f"{path} is not a file")
        if images_dir is not None and not images_dir.is_dir():
            raise CommandError(f"{images_dir} is not a folder")
        try:
            report = import_catalog(
                path, dry_run=options["dry_run"], images_dir=images_dir
            )
        except MissingColumns as error:
            raise CommandError(str(error)) from None

        if report.ignored_columns:
            self.stdout.write("Ignored columns: " + ", ".join(report.ignored_columns))
        if not report.ok:
            for row_error in report.errors:
                self.stderr.write(str(row_error))
            raise CommandError(
                f"{len(report.errors)} error(s) in {path.name}; nothing was imported"
            )
        prefix = "Dry run, nothing written: " if report.dry_run else ""
        self.stdout.write(
            f"{prefix}{report.created} created, {report.updated} updated, "
            f"{report.unchanged} unchanged "
            f"({report.products_created} new products, {report.images_added} images)"
        )
        for label, count in report.created_lookups.items():
            self.stdout.write(f"  new {label}: {count}")
