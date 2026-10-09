"""Auto-discover and register all provider adapters.

Import this module to populate the global registry with every
available adapter. Adapters that lack dependencies or configuration
are registered but report themselves as unavailable at runtime.

P1-02 (2026-10-09): each import used to be swallowed by a bare
``except ImportError: pass``, so a missing dependency left the registry
silently incomplete — a broken deployment looked like a feature that was
simply not configured. Every failure is now recorded and exposed through
:func:`load_failures`, so a startup check and ``/health/detailed`` can say
which adapters did not load.
"""

from .base import registry

import importlib

# Every adapter the suite knows how to drive. ``load_failures()`` reports the
# ones that did not import, so an incomplete registry is never silent.
_DECLARED = (
    ("bright_data", ".brightdata", "BrightDataAdapter"),
    ("easy_parser", ".easy_parser", "EasyParserAdapter"),
    ("openwebninja", ".open_web_ninja", "OpenWebNinjaAdapter"),
    ("amazon_api", ".amazon_api", "AmazonAPIAdapter"),
    ("scrape_do", ".scrape_do", "ScrapeDoAdapter"),
    ("firecrawl", ".firecrawl", "FirecrawlAdapter"),
)

load_failures: list[dict] = []


def _try_register(key: str, module_name: str, class_name: str) -> bool:
    try:
        module = importlib.import_module(module_name, package=__package__)
        adapter_class = getattr(module, class_name)
    except ImportError as exc:
        load_failures.append({
            "adapter": key,
            "module": module_name.lstrip("."),
            "error": "ImportError: %s" % exc,
        })
        return False
    registry.register(key, adapter_class)
    return True


for _key, _module_name, _class_name in _DECLARED:
    _try_register(_key, _module_name, _class_name)
