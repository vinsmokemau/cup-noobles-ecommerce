"""The user model (§4.4). Staff sign in to the admin with it in Release 1."""

import uuid
from typing import ClassVar

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.db import GEN_RANDOM_UUID, NOW
from apps.core.fields import CIEmailField, FixedCharField


class CustomerManager(BaseUserManager["Customer"]):
    use_in_migrations = True

    def _create(self, email: str, password: str | None, **extra) -> "Customer":
        if not email:
            raise ValueError("An email is required.")
        customer = self.model(email=self.normalize_email(email), **extra)
        customer.set_password(password)
        customer.save(using=self._db)
        return customer

    def create_user(
        self, email: str, password: str | None = None, **extra
    ) -> "Customer":
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(
        self, email: str, password: str | None = None, **extra
    ) -> "Customer":
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if not (extra["is_staff"] and extra["is_superuser"]):
            raise ValueError("A superuser needs is_staff=True and is_superuser=True.")
        return self._create(email, password, **extra)


class Customer(AbstractBaseUser):
    """Django's AUTH_USER_MODEL.

    `PermissionsMixin` is not used: its group and permission tables are not in
    `spec/schema.sql` (P2-V01 allows no other application table). Only a superuser
    holds permissions until the spec defines staff roles.
    """

    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4, db_default=GEN_RANDOM_UUID, unique=True, editable=False
    )
    email = CIEmailField(unique=True)
    password = models.TextField("password")
    full_name = models.TextField(default="", db_default="", blank=True)
    phone = models.TextField(default="", db_default="", blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    accepts_marketing = models.BooleanField(default=False, db_default=False)
    is_active = models.BooleanField(default=True, db_default=True)
    is_staff = models.BooleanField(default=False, db_default=False)
    is_superuser = models.BooleanField(default=False, db_default=False)
    date_joined = models.DateTimeField(default=timezone.now, db_default=NOW)

    objects = CustomerManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    class Meta:
        db_table = "customer"

    def __str__(self) -> str:
        return self.email

    def has_perm(self, perm: str, obj: object = None) -> bool:
        return self.is_active and self.is_superuser

    def has_module_perms(self, app_label: str) -> bool:
        return self.is_active and self.is_superuser


class Address(models.Model):
    """A saved delivery address. Unused in Release 1 (§4.4): orders freeze a snapshot instead."""

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="addresses", db_index=False
    )
    label = models.TextField(default="", db_default="", blank=True)
    recipient_name = models.TextField()
    phone = models.TextField()
    street = models.TextField()
    ext_number = models.TextField()
    int_number = models.TextField(default="", db_default="", blank=True)
    neighborhood = models.TextField()
    municipality = models.TextField()
    state = models.ForeignKey(
        "shipping.MxState",
        on_delete=models.DO_NOTHING,
        db_column="state_code",
        db_index=False,
    )
    postal_code = FixedCharField(max_length=5)
    delivery_notes = models.TextField(default="", db_default="", blank=True)
    is_default = models.BooleanField(default=False, db_default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_default=NOW)
    updated_at = models.DateTimeField(auto_now=True, db_default=NOW)

    class Meta:
        db_table = "address"
        constraints = [
            models.CheckConstraint(
                condition=Q(postal_code__regex=r"^[0-9]{5}$"),
                name="address_postal_code_check",
            ),
            models.UniqueConstraint(
                fields=["customer"],
                condition=Q(is_default=True, deleted_at__isnull=True),
                name="address_single_default_uq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["customer"],
                condition=Q(deleted_at__isnull=True),
                name="address_customer_idx",
            )
        ]
