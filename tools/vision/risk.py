"""Risk classes for every input action, decided before the action runs.

Work order §5.1 layer 4 and §2. Every input action carries a class. The class is
decided *before* the action executes and re-decided *after* any navigation, because a
redirect can move an action onto a host that was never approved.

| class | meaning | allowed |
|---|---|---|
| `observe` | read the tree, the DOM or the pixels | yes |
| `navigate` | move a window, a tab or a page without changing external state | yes |
| `edit_own` | change our own app, our own files, our own window | yes, inside the declared scope |
| `external_irreversible` | post, send, delete, purchase, checkout, log in | **no** — `needs_you.md` |
| `blocked` | Amazon or a privacy-blocklisted window, credential entry, CAPTCHA | **no** — never |

The two refusal classes are the hard lines, so they are enforced here rather than in the
callers: a caller that forgets to ask is the failure mode this module exists to remove.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from . import privacy

ROOT = Path(__file__).resolve().parents[2]
NEEDS = ROOT / "reports" / "ty" / "needs_you.md"
EVENTS = ROOT / "state" / "vision" / "events.jsonl"

OBSERVE = "observe"
NAVIGATE = "navigate"
EDIT_OWN = "edit_own"
EXTERNAL_IRREVERSIBLE = "external_irreversible"
BLOCKED = "blocked"

ORDER = (OBSERVE, NAVIGATE, EDIT_OWN, EXTERNAL_IRREVERSIBLE, BLOCKED)
RANK = {name: index for index, name in enumerate(ORDER)}

#: Action kinds mapped to the least dangerous class that can describe them. An unknown
#: kind is `external_irreversible` on purpose: silence must not read as permission.
ACTION_RISK: Dict[str, str] = {
    # observe
    "screenshot": OBSERVE, "capture": OBSERVE, "read_tree": OBSERVE, "read_dom": OBSERVE,
    "find": OBSERVE, "describe": OBSERVE, "read_text": OBSERVE, "list_windows": OBSERVE,
    "wait": OBSERVE, "hover": OBSERVE,
    # navigate
    "navigate": NAVIGATE, "open_url": NAVIGATE, "scroll": NAVIGATE, "switch_tab": NAVIGATE,
    "focus_window": NAVIGATE, "back": NAVIGATE, "forward": NAVIGATE, "reload": NAVIGATE,
    # edit own app or own files
    "click": EDIT_OWN, "type": EDIT_OWN, "press": EDIT_OWN, "select": EDIT_OWN,
    "save": EDIT_OWN, "create_file": EDIT_OWN, "edit_file": EDIT_OWN,
    "launch_app": EDIT_OWN, "close_window": EDIT_OWN, "drag": EDIT_OWN,
    # external irreversible
    "submit": EXTERNAL_IRREVERSIBLE, "send": EXTERNAL_IRREVERSIBLE,
    "post": EXTERNAL_IRREVERSIBLE, "delete": EXTERNAL_IRREVERSIBLE,
    "purchase": EXTERNAL_IRREVERSIBLE, "checkout": EXTERNAL_IRREVERSIBLE,
    "pay": EXTERNAL_IRREVERSIBLE, "log_in": EXTERNAL_IRREVERSIBLE,
    "sign_in": EXTERNAL_IRREVERSIBLE, "enter_password": EXTERNAL_IRREVERSIBLE,
    "solve_captcha": EXTERNAL_IRREVERSIBLE, "upload_external": EXTERNAL_IRREVERSIBLE,
    "accept_terms": EXTERNAL_IRREVERSIBLE, "subscribe": EXTERNAL_IRREVERSIBLE,
    # never
    "enter_payment": BLOCKED, "read_credential": BLOCKED,
}

#: Words in a field name that mean the value is not ours to type.
CREDENTIAL_WORDS = ("password", "passwd", "passcode", "card number", "credit card",
                    "cvv", "cvc", "security code", "iban", "account number", "pin")

#: Hosts we own. Anything else is external, and external is read-only.
OWN_HOSTS = ("localhost", "127.0.0.1", "::1", "0.0.0.0")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def infer(action: Dict[str, Any]) -> str:
    """The risk class for one action, before any policy context is considered."""
    kind = str(action.get("kind") or "").strip().casefold()
    if not kind:
        return EXTERNAL_IRREVERSIBLE
    return ACTION_RISK.get(kind, EXTERNAL_IRREVERSIBLE)


def _host(url: str) -> str:
    text = str(url or "").strip()
    if "://" not in text:
        return ""
    rest = text.split("://", 1)[1]
    return rest.split("/", 1)[0].split(":", 1)[0].casefold()


def is_own_url(url: str) -> bool:
    host = _host(url)
    if not host:
        return str(url or "").startswith("file://")
    return host in OWN_HOSTS or host.endswith(".localhost")


def _credential_target(action: Dict[str, Any]) -> str:
    haystack = " ".join(str(action.get(key) or "") for key in
                        ("target", "field", "label", "role", "name")).casefold()
    for word in CREDENTIAL_WORDS:
        if word in haystack:
            return word
    return ""


def evaluate(action: Dict[str, Any], *, url: str = "", title: str = "",
             process: str = "", scope: Optional[Iterable[str]] = None,
             own_hosts: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Allow or refuse one action. A refusal names the class and the reason.

    `url`/`title`/`process` are the *current* context, so the same action re-evaluated
    after a redirect can flip from allowed to refused without the caller changing it.
    """
    risk = infer(action)
    # The screen-privacy blocklist is absolute and is checked first, before the action
    # kind gets a say: an observe on an Amazon window is still an Amazon interaction.
    verdict = privacy.classify(title=title, process=process, url=url)
    if not verdict.get("allow"):
        return {"allow": False, "risk": BLOCKED, "needs_you": False,
                "reason": f"blocked context: {verdict.get('reason')}"}

    if risk == BLOCKED:
        return {"allow": False, "risk": BLOCKED, "needs_you": True,
                "reason": f"{action.get('kind')} is never performed by Ty"}

    if action.get("kind") == "type":
        word = _credential_target(action)
        if word:
            return {"allow": False, "risk": BLOCKED, "needs_you": True,
                    "reason": f"refusing to type into a credential field ({word!r})"}

    if risk == EXTERNAL_IRREVERSIBLE:
        return {"allow": False, "risk": EXTERNAL_IRREVERSIBLE, "needs_you": True,
                "reason": (f"{action.get('kind')!r} changes state outside this machine "
                           "and is irreversible; it needs the owner")}

    if risk == EDIT_OWN:
        path = str(action.get("path") or "")
        if path and scope is not None and not _in_scope(path, scope):
            return {"allow": False, "risk": EDIT_OWN, "needs_you": True,
                    "reason": f"{path!r} is outside the declared write scope"}
        hosts = {h.casefold() for h in (own_hosts or OWN_HOSTS)}
        host = _host(url)
        if host and host not in hosts and not is_own_url(url):
            # A click or a keystroke on an external page is not ours to perform: it is
            # how a form gets submitted by accident. Reading the page is still fine.
            return {"allow": False, "risk": EXTERNAL_IRREVERSIBLE, "needs_you": True,
                    "reason": (f"edit on external host {host!r}; external pages are "
                               "read-only, so this needs the owner")}
    return {"allow": True, "risk": risk, "needs_you": False, "reason": ""}


def _in_scope(path: str, scope: Iterable[str]) -> bool:
    from pathlib import Path as _Path

    def norm(value: str) -> str:
        return str(_Path(value).as_posix()).strip("/").casefold()

    target = norm(path)
    base = norm(str(ROOT))
    for root in scope:
        candidate = norm(root)
        if candidate.startswith(base):
            candidate = candidate[len(base):].lstrip("/")
        if target == candidate or target.startswith(candidate + "/"):
            return True
    return False


def record_needs_you(action: Dict[str, Any], verdict: Dict[str, Any],
                     *, needs: Optional[Path] = None) -> str:
    """Queue one exact owner action. This is the only side effect a refusal has."""
    path = Path(needs or NEEDS)
    line = (f"- {_now()} **{verdict.get('risk')}** — {verdict.get('reason')} "
            f"| action: `{json.dumps(action, ensure_ascii=False)[:300]}`\n")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        return ""
    return line


def record_event(row: Dict[str, Any], *, events: Optional[Path] = None) -> None:
    path = Path(events or EVENTS)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": _now(), **row}, ensure_ascii=False) + "\n")
    except OSError:
        pass


__all__ = ["OBSERVE", "NAVIGATE", "EDIT_OWN", "EXTERNAL_IRREVERSIBLE", "BLOCKED",
           "ACTION_RISK", "infer", "evaluate", "is_own_url", "record_needs_you",
           "record_event"]
