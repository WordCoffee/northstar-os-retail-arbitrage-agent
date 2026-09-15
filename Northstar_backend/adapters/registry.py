"""Auto-discover and register all provider adapters.

Import this module to populate the global registry with every
available adapter. Adapters that lack dependencies or configuration
are registered but report themselves as unavailable at runtime.
"""

from .base import registry

# Import all adapter classes
try:
    from .brightdata import BrightDataAdapter
    registry.register("bright_data", BrightDataAdapter)
except ImportError:
    pass

try:
    from .easy_parser import EasyParserAdapter
    registry.register("easy_parser", EasyParserAdapter)
except ImportError:
    pass

try:
    from .open_web_ninja import OpenWebNinjaAdapter
    registry.register("openwebninja", OpenWebNinjaAdapter)
except ImportError:
    pass

try:
    from .amazon_api import AmazonAPIAdapter
    registry.register("amazon_api", AmazonAPIAdapter)
except ImportError:
    pass

try:
    from .scrape_do import ScrapeDoAdapter
    registry.register("scrape_do", ScrapeDoAdapter)
except ImportError:
    pass

try:
    from .firecrawl import FirecrawlAdapter
    registry.register("firecrawl", FirecrawlAdapter)
except ImportError:
    pass
