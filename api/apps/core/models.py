"""Site-wide settings that staff edit in the admin (SPEC.md §4.4, G32, ADR-0038)."""

from django.db import models
from django.db.models import Q

from apps.core.db import NOW


class SiteSetting(models.Model):
    """The single row (`id = 1`). `prelaunch_mode` hides the public catalog; it is off by default."""

    id = models.SmallIntegerField(primary_key=True, default=1, db_default=1)
    prelaunch_mode = models.BooleanField(default=False, db_default=False)
    updated_at = models.DateTimeField(auto_now=True, db_default=NOW)

    class Meta:
        db_table = "site_setting"
        constraints = [
            models.CheckConstraint(condition=Q(id=1), name="site_setting_id_check")
        ]

    def __str__(self) -> str:
        return "Configuración del sitio"

    @classmethod
    def prelaunch_active(cls) -> bool:
        """True while the catalog is hidden from the public. A missing row means off."""
        return bool(
            cls.objects.filter(pk=1).values_list("prelaunch_mode", flat=True).first()
        )
