"""Role resolution: a role is a capability, a chain is an ordered list of providers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
ROLES_PATH = Path(os.environ.get("NORTHSTAR_MODEL_ROLES",
                                 ROOT / "shared" / "model-roles.json"))

VALID_ROLES = ("reasoning", "tool_calling", "image", "video", "voice", "embeddings")


def load() -> Dict[str, Any]:
    try:
        return json.loads(Path(ROLES_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # Fail CLOSED: an unreadable role map must not silently pick a provider.
        return {"roles": {}}


def chain(role: str) -> List[str]:
    """Provider chain for a role, honouring a per-role env override.

    `NORTHSTAR_ROLE_<ROLE>=stub_cloud` swaps one role without touching the file;
    `NORTHSTAR_FORCE_PROVIDER=stub_cloud` swaps every role (the acceptance test).
    """
    if role not in VALID_ROLES:
        raise ValueError(f"unknown role {role!r}; known: {', '.join(VALID_ROLES)}")
    forced = os.environ.get("NORTHSTAR_FORCE_PROVIDER", "").strip()
    if forced:
        return [forced]
    override = os.environ.get(f"NORTHSTAR_ROLE_{role.upper()}", "").strip()
    if override:
        return [p.strip() for p in override.split(",") if p.strip()]
    spec = (load().get("roles") or {}).get(role) or {}
    providers = [p for p in (spec.get("chain") or []) if p]
    if not providers:
        raise ValueError(f"role {role!r} has no provider chain configured")
    return providers


def model_for(role: str, provider: str) -> Optional[str]:
    spec = (load().get("roles") or {}).get(role) or {}
    if provider.startswith("local"):
        return spec.get("local_model")
    return spec.get(f"{provider}_model") or spec.get("local_model")


def describe() -> Dict[str, Any]:
    out = {}
    for role in VALID_ROLES:
        try:
            out[role] = chain(role)
        except ValueError as exc:
            out[role] = {"error": str(exc)}
    return out
