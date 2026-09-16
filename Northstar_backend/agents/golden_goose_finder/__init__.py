"""Golden Goose Finder — Multi-pack breakdown arbitrage scanner.

Exposes the shared data models and the public scoring/reporting API.
The sibling economics module should import the data models from here:
``from Northstar_backend.agents.golden_goose_finder import BreakdownEconomics``
"""

from .opportunity_scorer import (
    BreakdownEconomics,
    IndividualListing,
    ScoredOpportunity,
    WholesalePack,
    get_scoring_summary,
    score_batch,
    score_opportunity,
)
from .goose_report import (
    export_to_scout_panel,
    generate_console_display,
    generate_json_report,
    save_report,
)

__version__ = "0.1.0"

__all__ = [
    "BreakdownEconomics",
    "IndividualListing",
    "WholesalePack",
    "ScoredOpportunity",
    "score_opportunity",
    "score_batch",
    "get_scoring_summary",
    "generate_json_report",
    "save_report",
    "generate_console_display",
    "export_to_scout_panel",
]