"""Local development: every provider on its mock, dev tools on (§4.7)."""

from .base import *
from .base import env

DEBUG = True
DEV_TOOLS_ENABLED = env.bool("DEV_TOOLS_ENABLED", default=True)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost"])
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS", default=["http://localhost:8080"]
)
