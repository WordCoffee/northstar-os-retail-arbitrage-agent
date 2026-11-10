"""Specialist agents behind Bojo.

Bojo is a ROUTER (see router.py) and never does specialist work itself. Each
module here owns one job, declares the inputs it cannot work without, and
returns a validated result.

Provenance: every module is REBUILT from a behaviour spec in /specs. None is
adapted from another project's source, so nothing here inherits a third-party
licence. Where a spec could not be completed by observing a target (no repo
cloned, no hosted access this session) the corresponding spec row is marked
UNVERIFIED and the build uses Northstar's own architecture only.
"""

from __future__ import annotations

__all__ = ["registry", "router", "package_designer", "listing_optimizer",
           "ppc_agent", "validation"]
