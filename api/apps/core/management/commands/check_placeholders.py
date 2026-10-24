"""Exit non-zero while a Part A stand-in remains (SPEC.md §2.5, REQ-065).

The Phase 22 launch checklist requires exit 0 against production.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.core.placeholders import find_placeholders


class Command(BaseCommand):
    help = "Fail while any placeholder, demo row or dev default remains (SPEC.md §2.5)."

    def handle(self, *args: Any, **options: Any) -> None:
        findings = find_placeholders()
        if findings:
            listing = "\n  ".join(findings)
            raise CommandError(
                f"check_placeholders: {len(findings)} placeholder(s) remain:\n  {listing}"
            )
        self.stdout.write("check_placeholders: none remain")
