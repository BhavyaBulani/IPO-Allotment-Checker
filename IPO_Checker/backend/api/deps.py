"""Shared FastAPI dependencies.

The previous admin API-key dependency has been replaced by bearer-token auth in
``api.security``. This module keeps a single import point so endpoints don't
need to know where the dependency lives.
"""

from api.security import require_auth  # noqa: F401
