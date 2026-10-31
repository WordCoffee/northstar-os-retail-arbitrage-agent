"""Brand memory synchronisation (Phase 3, item 3).

Every creative run should teach the account something: its colours, its fonts,
where the logo sits, and which prompts actually produced good work. This module
extracts those into memory atoms.

THE GATE: an agent may not silently rewrite an account's memory. This module
produces a **proposal**; the status is always `"proposed"` and nothing is written
unless the caller supplies an explicit `store` callable (the operator-approved
path). There is no code path here that returns `"applied"`.

Pure extraction + a single injected write, so it is fully testable.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, Iterable, List, Optional

HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
MAX_COLORS = 8
MAX_PROMPTS = 10
PROMPT_MAX_CHARS = 600
STATUS = "proposed"


def _hex(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    v = value.strip()
    if not HEX.match(v):
        return None
    if len(v) == 4:                       # #abc -> #aabbcc
        v = "#" + "".join(c * 2 for c in v[1:])
    return v.lower()


def _text(value: Any, limit: int = 120) -> Optional[str]:
    if not isinstance(value, str):
        return None
    v = " ".join(value.strip().split())
    return v[:limit] if v else None


def extract(profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Pull brand tokens out of an account profile. Junk is dropped, not guessed."""
    profile = profile or {}
    brand = profile.get("brand") if isinstance(profile.get("brand"), dict) else profile.get("brand") or {}

    colours: List[str] = []
    seen = set()
    raw_colours = list(brand.get("colors") or brand.get("colours") or []) if isinstance(brand, dict) else []
    for c in raw_colours:
        h = _hex(c)
        if h and h not in seen:
            seen.add(h)
            colours.append(h)
        if len(colours) >= MAX_COLORS:
            break

    fonts_raw = brand.get("fonts") if isinstance(brand.get("fonts"), dict) else {}
    fonts = {}
    for role in ("heading", "body"):
        v = _text(fonts_raw.get(role), 60)
        if v:
            fonts[role] = v

    logo_raw = brand.get("logo") if isinstance(brand.get("logo"), dict) else {}
    logo = {}
    ref = _text(logo_raw.get("ref"), 300)
    if ref:
        logo["ref"] = ref
    placement = _text(logo_raw.get("placement"), 60)
    if placement:
        logo["placement"] = placement.lower()

    prompts: List[str] = []
    p_seen = set()
    for p in (brand.get("prompts") or brand.get("visual_prompts") or [])[: MAX_PROMPTS * 2]:
        t = _text(p, PROMPT_MAX_CHARS)
        if t and t.lower() not in p_seen:
            p_seen.add(t.lower())
            prompts.append(t)
        if len(prompts) >= MAX_PROMPTS:
            break

    return {"colors": colours, "fonts": fonts, "logo": logo, "prompts": prompts}


def atoms(brand: Dict[str, Any], account_id: str) -> List[Dict[str, Any]]:
    """Flatten to memory atoms. Keys are stable so a re-run updates, not duplicates."""
    out: List[Dict[str, Any]] = []
    acct = str(account_id or "default")
    for i, colour in enumerate(brand.get("colors") or []):
        out.append({"account_id": acct, "kind": "brand", "key": f"brand.color.{i}",
                    "value": colour, "status": STATUS})
    for role, family in (brand.get("fonts") or {}).items():
        out.append({"account_id": acct, "kind": "brand", "key": f"brand.font.{role}",
                    "value": family, "status": STATUS})
    for field, value in (brand.get("logo") or {}).items():
        out.append({"account_id": acct, "kind": "brand", "key": f"brand.logo.{field}",
                    "value": value, "status": STATUS})
    for i, prompt in enumerate(brand.get("prompts") or []):
        out.append({"account_id": acct, "kind": "prompt", "key": f"brand.prompt.{i}",
                    "value": prompt, "status": STATUS})
    return out


def merge(existing: Iterable[Dict[str, Any]], incoming: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Incoming wins on key; order follows first appearance."""
    merged: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for item in list(existing or []) + list(incoming or []):
        key = str(item.get("key") or "")
        if not key:
            continue
        if key not in merged:
            order.append(key)
        merged[key] = dict(item)
    return [merged[k] for k in order]


def propose(
    brand: Dict[str, Any],
    *,
    account_id: str,
    store: Optional[Callable[[List[Dict[str, Any]]], Any]] = None,
    note: str = "creative loop: brand tokens observed during a render",
) -> Dict[str, Any]:
    """Return a proposal document. Writes only through an injected `store`."""
    records = atoms(brand, account_id)
    doc: Dict[str, Any] = {
        "account_id": str(account_id or "default"),
        "status": STATUS,
        "note": note,
        "atoms": records,
        "count": len(records),
        "persisted": False,
        "reason": "no_store_supplied" if store is None else "",
    }
    if store is not None and records:
        try:
            store(records)
            doc["persisted"] = True
            doc["reason"] = ""
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed silently
            doc["persisted"] = False
            doc["reason"] = f"{type(exc).__name__}: {exc}"[:200]
    return doc


__all__ = ["extract", "atoms", "merge", "propose", "STATUS",
           "MAX_COLORS", "MAX_PROMPTS", "PROMPT_MAX_CHARS"]
