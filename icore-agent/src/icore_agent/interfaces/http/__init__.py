"""HTTP API adapter layer."""

from .v1.router import include_api_routers

__all__ = ["include_api_routers"]
