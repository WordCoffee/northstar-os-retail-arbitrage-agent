"""Provider adapter layer for Northstar OS.

Each adapter wraps a third-party provider behind a uniform BaseAdapter
interface and ProviderResponse contract so callers never touch transport
details, auth wiring, or error taxonomy directly.
"""

from .base import BaseAdapter, AdapterRegistry, ProviderResponse, ProviderStatus

# Import registry to auto-register all adapters
try:
    from . import registry  # noqa: F401
except ImportError:
    pass

__all__ = ["BaseAdapter", "AdapterRegistry", "ProviderResponse", "ProviderStatus"]
