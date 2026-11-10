"""Provider sign-in gate + CLI.

Between provider sign-ins, this pipeline PROMPTS the operator to sign in to the
research browser (Costco Business Center, SellerAmp SAS). A sign-in
is recorded as a durable confirmation (default TTL) in the canonical DB.

Rules:
  * The pipeline never automates login, never extracts cookies, and never reuses
    sessions programmatically.
  * `require_signin()` returns a prompt; the agent must surface it and wait.
  * `mark_signed_in()` is the operator's explicit confirmation that they signed in.
  * Everything is fail-closed: enrichment/import stages that need a service prompt
    until the operator confirms.
  * Retired services (SellerSprite) fail closed by name.

CLI:
    python -m costco_non_kirkland.signin --service selleramp --check
    python -m costco_non_kirkland.signin --service selleramp --done
    python -m costco_non_kirkland.signin --service costco --prompt
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .enums import SignInService, SIGN_IN_SERVICES
from .providers import RETIRED_PROVIDERS

# Service -> sign-in URL (documented; deep links never imply fetched data).
SIGN_IN_URLS: Dict[str, str] = {
    SignInService.COSTCO.value: "https://www.costco.com/",
    SignInService.SELLERAMP.value: "https://sas.selleramp.com/",
}

# Optional env override to mark a service pre-signed-in (non-secret operator flag).
SIGNED_IN_ENV = {
    SignInService.COSTCO.value: "NORTHSTAR_COSTCO_SIGNED_IN",
    SignInService.SELLERAMP.value: "NORTHSTAR_SELLERAMP_SIGNED_IN",
}

# Default sign-in confirmation TTL (6 hours).
DEFAULT_SIGNIN_TTL_MS = 6 * 60 * 60 * 1000


@dataclass
class SignInPrompt:
    required: bool
    service: str
    url: Optional[str]
    message: str
    signed_in: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "required": self.required,
            "service": self.service,
            "url": self.url,
            "message": self.message,
            "signed_in": self.signed_in,
        }


def _env_signed_in(service: str) -> bool:
    env = SIGNED_IN_ENV.get(service)
    if not env:
        return False
    return (os.getenv(env) or "").strip().lower() in ("1", "true", "yes", "on")


def _service_valid(service: str) -> bool:
    return service in SIGN_IN_URLS


def require_signin(service: str, *, store: Optional[Any] = None,
                   ttl_ms: Optional[int] = None) -> SignInPrompt:
    """Return a SignInPrompt for a service.

    If a valid, unexpired sign-in confirmation already exists (or the env flag is
    set), the prompt reports `required=False`. Otherwise the prompt instructs the
    operator to sign in to the research browser and confirm.
    """
    service = (service or "").lower()
    if service in RETIRED_PROVIDERS:
        return SignInPrompt(required=True, service=service, url=None,
                            message=f"Service {service!r} is retired — {RETIRED_PROVIDERS[service]}")
    if not _service_valid(service):
        return SignInPrompt(required=True, service=service, url=None,
                            message=f"Unknown sign-in service: {service!r}")
    if _env_signed_in(service):
        return SignInPrompt(required=False, service=service, url=SIGN_IN_URLS[service],
                            message="Sign-in already confirmed via env flag.", signed_in=True)

    confirmed = False
    if store is not None:
        try:
            confirmed = store.has_confirmation(f"signin:{service}")
        except Exception:
            confirmed = False
    if confirmed:
        return SignInPrompt(required=False, service=service, url=SIGN_IN_URLS[service],
                            message="Sign-in confirmation present.", signed_in=True)

    url = SIGN_IN_URLS[service]
    return SignInPrompt(
        required=True, service=service, url=url,
        message=(
            f"[SIGN-IN REQUIRED] Please sign in to {service} in the Northstar research "
            f"browser at {url}, then confirm with:\n"
            f"  python -m costco_non_kirkland.signin --service {service} --done"
        ),
    )


def mark_signed_in(service: str, *, store: Optional[Any] = None,
                   granted_by: str = "operator",
                   ttl_ms: Optional[int] = None) -> Dict[str, Any]:
    """Record an explicit operator confirmation that sign-in is complete."""
    service = (service or "").lower()
    if service in RETIRED_PROVIDERS:
        return {"ok": False, "error": f"Service {service!r} is retired.",
                "reason": "retired_provider", "detail": RETIRED_PROVIDERS[service],
                "allowed": list(SIGN_IN_URLS.keys())}
    if not _service_valid(service):
        return {"ok": False, "error": f"Unknown sign-in service: {service!r}",
                "allowed": list(SIGN_IN_URLS.keys())}
    if store is None:
        from .store import PipelineStore
        store = PipelineStore()
    store.grant_confirmation(f"signin:{service}", f"Operator signed in to {service}",
                             granted_by=granted_by,
                             expires_in_ms=ttl_ms or DEFAULT_SIGNIN_TTL_MS)
    return {"ok": True, "service": service, "signed_in": True,
            "url": SIGN_IN_URLS[service], "ttl_ms": ttl_ms or DEFAULT_SIGNIN_TTL_MS}


def require_signin_prompt_all(services: Optional[List[str]] = None, *, store=None) -> List[Dict[str, Any]]:
    """Batch-query sign-in prompts for a list of services (defaults to all)."""
    services = services or list(SIGN_IN_URLS.keys())
    return [require_signin(s, store=store).to_dict() for s in services]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    argv = list(argv) if argv is not None else list(sys.argv[1:])
    if "--service" not in argv:
        print("error: missing --service", file=sys.stderr)
        print("allowed:", ", ".join(SIGN_IN_SERVICES), file=sys.stderr)
        return 2
    service = argv[argv.index("--service") + 1].lower()
    if service not in SIGN_IN_SERVICES:
        print(f"error: unknown service {service!r}; allowed: {', '.join(SIGN_IN_SERVICES)}", file=sys.stderr)
        return 2

    store = None
    try:
        from .store import PipelineStore
        store = PipelineStore()
    except Exception:
        store = None

    if "--done" in argv:
        from .cli_common import print_json, print_network_confirmation
        out = mark_signed_in(service, store=store)
        print_network_confirmation(0)
        print_json(out)
        return 0 if out.get("ok") else 2
    if "--prompt" in argv:
        from .cli_common import print_json, print_network_confirmation
        print_network_confirmation(0)
        print_json(require_signin(service, store=store).to_dict())
        return 0
    # default: --check
    from .cli_common import print_json, print_network_confirmation
    result = require_signin(service, store=store)
    print_network_confirmation(0)
    print_json(result.to_dict())
    return 0 if not result.required else 1


if __name__ == "__main__":
    sys.exit(main())