"""Stable config exports for backend callers and frontend integration.

Import from this package when you need:

- `Config`: runtime configuration object used by the backend service/agent.
- `ConfigFactory`: canonical constructor plus frontend-facing defaults/schema.
- `FRONTEND_DEPLOYMENT_CHOICES`: deployment labels that the UI may surface.

The frontend should not invent its own defaults or editable-field list.
Those decisions live in `ConfigFactory`.
"""

from .frontend_schema import FRONTEND_DEPLOYMENT_CHOICES
from .settings import Config, ConfigFactory

__all__ = ["Config", "ConfigFactory", "FRONTEND_DEPLOYMENT_CHOICES"]
