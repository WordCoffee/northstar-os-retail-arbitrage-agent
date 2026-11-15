"""The Bojo tool registry: one place that knows which tools exist.

Each domain module exports ``TOOLS = {name: callable}``. This module aggregates them and
answers the one question the chat surface asks — "is there a handler for this name?" — so a
service can be driven by Bojo only when the handler is real.

Adding a module is deliberate: a tool that is declared on a service but missing here is a gap
the scorecard shows as `complete`, not something to paper over.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List

_MODULES = (
    "bojo_tools.sourcing",
    "bojo_tools.sourcing_extra",
    "bojo_tools.publishing",
    "bojo_tools.keywords",
    "bojo_tools.competitors",
    "bojo_tools.economics",
    "bojo_tools.campaigns",
    "bojo_tools.foundation_ops",
    "bojo_tools.design",
    "bojo_tools_ops",
    "bojo_tools.research_toolkit",
)

#: Retired domain tools: name → one-line reason. The handler stays in its module and
#: still answers a direct ``call``; it is simply never offered. Retirement is not
#: deletion — prove the tool dead first.
RETIRED: Dict[str, str] = {}


def _load(name: str) -> Dict[str, Callable[..., Any]]:
    try:
        module = __import__(name, fromlist=["TOOLS"])
    except Exception:  # noqa: BLE001 - a module that is not present contributes nothing
        return {}
    tools = getattr(module, "TOOLS", None)
    if not isinstance(tools, dict):
        return {}
    return {str(key): value for key, value in tools.items() if callable(value)}


def tools() -> Dict[str, Callable[..., Any]]:
    """Every domain handler that exists, retired ones included."""
    found: Dict[str, Callable[..., Any]] = {}
    for name in _MODULES:
        for tool_name, handler in _load(name).items():
            found.setdefault(tool_name, handler)
    return found


def has_handler(name: str) -> bool:
    """True when a callable handler exists for this name — the offer gate."""
    return callable(tools().get(str(name)))


def offered() -> List[str]:
    """The offered list: a callable handler exists and the tool is not retired.

    Derived, so a tool whose module lands later appears without editing a list, and
    a module that is missing contributes nothing instead of offering a dead name.
    """
    return sorted(name for name, handler in tools().items()
                  if callable(handler) and name not in RETIRED)


def names() -> List[str]:
    return offered()


def get(name: str) -> Callable[..., Any]:
    handler = tools().get(str(name))
    if handler is None:
        raise KeyError(f"no Bojo tool named {name!r}")
    return handler


def call(name: str, **kwargs: Any) -> Dict[str, Any]:
    """Call a tool by name and always answer with a dict."""
    try:
        handler = get(name)
    except KeyError as exc:
        return {"ok": False, "tool": name, "reason": str(exc)}
    try:
        result = handler(**kwargs)
    except TypeError as exc:
        return {"ok": False, "tool": name, "reason": f"bad arguments: {exc}"}
    except Exception as exc:  # noqa: BLE001 - a tool failure is reported, not raised
        return {"ok": False, "tool": name, "reason": f"{type(exc).__name__}: {exc}"}
    if isinstance(result, dict) and "ok" in result:
        return result
    return {"ok": True, "tool": name, "data": result}


__all__ = ["tools", "names", "offered", "has_handler", "RETIRED", "get", "call"]
