"""Local development: every provider on its mock, dev tools on (§4.7)."""

from .base import *
from .base import env

DEBUG = True
DEV_TOOLS_ENABLED = env.bool("DEV_TOOLS_ENABLED", default=True)

# The E2E stack turns the rate limits off (G66): every spec reaches the API from one address
# through Caddy, so the guest lookup's 5 per hour would fail the storefront specs. The limit
# itself is proven at the API (P6-V18). prod.py never reads this, so production keeps the limits.
RATELIMIT_ENABLE = env.bool("RATELIMIT_ENABLE", default=True)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost"])
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS", default=["http://localhost:8080"]
)
