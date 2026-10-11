"""Default-off gate for every Amazon-account LINKAGE path.

Architecture decision (2026-10-11): NorthstarOS never signs in to Amazon and
never links a seller's Amazon accounts. No SP-API, no Ads API, no LWA/OAuth, no
Amazon credentials. The file-only workflow is: the seller downloads files from
Amazon, uploads them here, Northstar writes a change file, and the seller
uploads that to Amazon manually.

Every path that could talk to Amazon on the seller's behalf (the SP-API
importer, the Ads API importer, the unified Amazon adapter, and the blacklist
re-check task's live branch) consults this gate and REFUSES unless
``NS_AMAZON_LINKAGE_ENABLED`` is an explicit opt-in. The gate itself is refused
at startup in staging/production: ``assert_linkage_posture()`` raises, so a
deploy that enables linkage cannot boot (mirroring the live-provider posture
guard).

The static scan in ``tools/test_no_amazon_linkage.py`` proves the file-only
surfaces contain no linkage code at all.
"""

import os
from typing import List, Optional

from env_flags import env_flag

LINKAGE_ENV = "NS_AMAZON_LINKAGE_ENABLED"

_PROD_LIKE = frozenset({"staging", "production"})


def linkage_enabled() -> bool:
    """True only when NS_AMAZON_LINKAGE_ENABLED is an explicit opt-in."""
    return env_flag(LINKAGE_ENV)


def _environment(env: Optional[str] = None) -> str:
    raw = env if env is not None else (os.environ.get("ENVIRONMENT") or "development")
    return raw.strip().lower()


def linkage_posture_problems(env: Optional[str] = None) -> List[str]:
    """Every reason the Amazon-linkage configuration must be refused."""
    problems: List[str] = []
    if _environment(env) in _PROD_LIKE and linkage_enabled():
        problems.append(
            "NS_AMAZON_LINKAGE_ENABLED is set in a production-like environment "
            f"(ENVIRONMENT={_environment(env)}). NorthstarOS is file-only: it "
            "never signs in to Amazon and never links seller accounts."
        )
    return problems


def assert_linkage_posture(env: Optional[str] = None) -> None:
    """Refuse to boot a production-like deploy with linkage enabled."""
    problems = linkage_posture_problems(env)
    if problems:
        raise RuntimeError("AMAZON LINKAGE POSTURE VIOLATION: " + "; ".join(problems))


def linkage_refusal_reason() -> str:
    """The stated reason an importer refuses, for logs and API payloads."""
    if not linkage_enabled():
        return (
            "Amazon account linkage is disabled by architecture: NorthstarOS is "
            "file-only (download from Amazon, upload here, upload the change "
            f"file back manually). Set {LINKAGE_ENV}=1 only for an explicitly "
            "approved development run."
        )
    return "Amazon linkage enabled by explicit opt-in."
