"""Load the 32 Mexican states into `mx_state` (SPEC.md §4.4, G41, ADR-0032).

Real reference data that every environment needs, so production runs it in the deploy step.
Idempotent. `seed_dev_defaults` calls the same function.
"""

from typing import Any

from django.core.management.base import BaseCommand

from apps.shipping.seeds import MX_STATES, seed_states


class Command(BaseCommand):
    help = "Seed the 32 Mexican states (ISO 3166-2:MX) into mx_state."

    def handle(self, *args: Any, **options: Any) -> None:
        seed_states()
        self.stdout.write(f"seed_states: {len(MX_STATES)} states")
