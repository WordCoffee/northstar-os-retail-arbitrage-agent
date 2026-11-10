"""Permission enforcement — the harness decides, not the prompt.

Order is fixed and matches the documented reference: **deny, then ask, then
allow**; the first matching rule wins and specificity never reorders. Two gates
are hardcoded and can never be granted by a plan: spending money/credits and any
Amazon host. A bare-tool deny removes the tool from the model's context.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .model import PermissionRule

AMAZON_HOST_RE = re.compile(
    r"(^|\.)(amazon\.[a-z.]+|amzn\.to|amazonaws\.com|media-amazon\.com|"
    r"ssl-images-amazon\.com|a\.co)$", re.I)
SPEND_RE = re.compile(
    r"\b(purchase|checkout|billing|charge|subscribe|top[_-]?up|buy[_-]?credits|"
    r"pay(ment)?|stripe|coinbase)\b", re.I)
CREDENTIAL_RE = re.compile(
    r"\b(credential|password|passwd|secret|api[_-]?key|token|enter[_-]?login|"
    r"solve[_-]?captcha|captcha)\b", re.I)
SIDE_EFFECT_RE = re.compile(
    r"^(bash|shell|exec|write|edit|delete|remove|browser_(click|type|submit|"
    r"navigate|form)|http_(post|put|delete)|purchase|checkout)", re.I)

#: Tools that are read-only by construction.
READ_ONLY_TOOLS = {"read", "grep", "glob", "list", "inspect", "search",
                   "corpus_search", "knowledge_lookup", "web_get", "http_get"}


class PermissionDenied(RuntimeError):
    def __init__(self, decision: "Decision"):
        super().__init__(f"{decision.effect}: {decision.reason}")
        self.decision = decision


@dataclass
class Decision:
    effect: str
    reason: str
    tool: str
    rule: Optional[PermissionRule] = None
    source: str = "mode"

    @property
    def allowed(self) -> bool:
        return self.effect == "allow"

    def to_dict(self) -> dict:
        return {"effect": self.effect, "reason": self.reason, "tool": self.tool,
                "source": self.source,
                "rule": self.rule.to_dict() if self.rule else None}


class Policy:
    """A small, deterministic policy engine.

    `mode` is one of the documented names: default, acceptEdits, plan, auto,
    dontAsk. `bypassPermissions` is deliberately unsupported.
    """

    def __init__(self, rules: Sequence[PermissionRule] = (), *, mode: str = "dontAsk",
                 allowed_paths: Sequence[str] = (), now: Optional[float] = None):
        self.rules: List[PermissionRule] = [r for r in rules if r.effect in
                                            ("deny", "ask", "allow")]
        self.mode = mode
        self.allowed_paths = [p.lower() for p in allowed_paths]
        self._now = now

    # ── hard gates ──────────────────────────────────────────────────────────
    @staticmethod
    def is_amazon_host(host: Optional[str]) -> bool:
        if not host:
            return False
        host = host.strip().lower().split("/")[0].split(":")[0]
        return bool(AMAZON_HOST_RE.search(host)) or "amazon" in host or "amzn.to" in host

    def evaluate(self, tool: str, specifier: str = "", *, host: Optional[str] = None,
                 action: Optional[str] = None, now: Optional[float] = None) -> Decision:
        tool = (tool or "").strip()
        specifier = specifier or ""
        action = action or ""
        blob = " ".join([tool, specifier, action])
        ts = self._now if now is None else now
        ts = time.time() if ts is None else ts

        # A host is checked against the live URL, so a redirect cannot smuggle
        # an action onto a refused host.
        if self.is_amazon_host(host):
            return Decision("deny", "Amazon is a standing owner gate", tool,
                            source="hardcoded")
        if SPEND_RE.search(blob):
            return Decision("deny", "spending money or paid credits is a standing "
                                    "owner gate", tool, source="hardcoded")
        if CREDENTIAL_RE.search(blob):
            return Decision("deny", "credential entry / CAPTCHA solving is never "
                                    "done by the agent", tool, source="hardcoded")

        for effect in ("deny", "ask", "allow"):
            for rule in self.rules:
                if rule.effect != effect:
                    continue
                if rule.expires_at is not None and ts > float(rule.expires_at):
                    continue
                if _rule_matches(rule, tool, specifier, host):
                    return Decision(effect, rule.why or f"rule: {rule.tool}",
                                    tool, rule=rule)

        return self._mode_decision(tool, specifier, host)

    def _mode_decision(self, tool: str, specifier: str,
                       host: Optional[str]) -> Decision:
        read_only = tool.lower() in READ_ONLY_TOOLS
        side_effect = bool(SIDE_EFFECT_RE.search(tool)) or not read_only
        if self.mode == "plan":
            if side_effect:
                return Decision("deny", "plan mode is side-effect free", tool,
                                source="mode:plan")
            return Decision("allow", "read-only in plan mode", tool, source="mode:plan")
        if self.mode == "dontAsk":
            if read_only:
                return Decision("allow", "read-only", tool, source="mode:dontAsk")
            return Decision("deny", "dontAsk denies anything that would prompt",
                            tool, source="mode:dontAsk")
        if self.mode == "acceptEdits":
            if read_only:
                return Decision("allow", "read-only", tool, source="mode:acceptEdits")
            if tool.lower() in ("write", "edit", "mkdir", "touch", "mv", "cp") and \
                    self._path_allowed(specifier):
                return Decision("allow", "edit inside the allowed paths", tool,
                                source="mode:acceptEdits")
            return Decision("ask", "outside the auto-accepted edits", tool,
                            source="mode:acceptEdits")
        if self.mode == "auto":
            if side_effect:
                return Decision("allow", "auto mode allows with an audit row", tool,
                                source="mode:auto")
            return Decision("allow", "read-only", tool, source="mode:auto")
        # default
        if read_only:
            return Decision("allow", "read-only", tool, source="mode:default")
        return Decision("ask", "manual approval required", tool, source="mode:default")

    def _path_allowed(self, path: str) -> bool:
        if not self.allowed_paths:
            return False
        p = (path or "").replace("\\", "/").lower()
        return any(p == a or p.startswith(a.rstrip("/") + "/") for a in self.allowed_paths)

    # ── helpers ─────────────────────────────────────────────────────────────
    def visible_tools(self, tools: Iterable[str]) -> List[str]:
        """Drop a tool entirely when a bare deny rule names it."""
        denied = {r.tool.lower() for r in self.rules
                  if r.effect == "deny" and not r.specifier}
        return [t for t in tools if t.lower() not in denied]

    def assert_allowed(self, tool: str, specifier: str = "", *,
                       host: Optional[str] = None, action: Optional[str] = None,
                       now: Optional[float] = None) -> Decision:
        d = self.evaluate(tool, specifier, host=host, action=action, now=now)
        if not d.allowed:
            raise PermissionDenied(d)
        return d

    def fingerprint(self) -> str:
        blob = json.dumps([r.to_dict() for r in self.rules] + [self.mode],
                          sort_keys=True).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:16]


def _rule_matches(rule: PermissionRule, tool: str, specifier: str,
                  host: Optional[str]) -> bool:
    if rule.tool.lower() != tool.lower():
        return False
    if not rule.specifier:
        return True
    spec = rule.specifier
    if spec.startswith("domain:") or spec.startswith("host:"):
        want = spec.split(":", 1)[1].lower()
        return bool(host) and (host.lower() == want or host.lower().endswith("." + want))
    return spec.lower() in specifier.lower()


def grant(tool: str, specifier: str = "", *, minutes: int = 60,
          why: str = "task grant", now: Optional[float] = None) -> PermissionRule:
    """A task-scoped allow that expires. No rule is permanent by default."""
    ts = time.time() if now is None else now
    return PermissionRule("allow", tool, specifier, scope="task",
                          expires_at=ts + minutes * 60, source="task_grant",
                          why=why)
