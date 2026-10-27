"""Chrome Connect compiler + replay + cache (Phase 3).

Converts successful AI loop traces into candidate adapters (PROPOSED).
Replays adapters on new pages; falls back to AI on mismatch; self-heals
selectors via fingerprint relocation.

Provenance: ADAPTED from Stagehand auto-caching (MIT, Browserbase) and
Scrapling adaptive selectors (BSD-3, D4Vinci). No code copied.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import chromeconnect_observation as obs

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------
CACHE_DIR = os.environ.get(
    "CC_CACHE_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data", "chromeconnect_cache"),
)
ADAPTER_DIR = os.environ.get(
    "CC_ADAPTER_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data", "chromeconnect_adapters"),
)
CACHE_TTL_S = int(os.environ.get("CC_CACHE_TTL_S", "86400"))  # 24h default


# ---------------------------------------------------------------------------
# Trace recorder
# ---------------------------------------------------------------------------

@dataclass
class TraceStep:
    step: int
    tool: str
    args: Dict[str, Any]
    success: bool
    post_condition_met: bool
    output: Any = None
    error: Optional[str] = None
    timestamp: float = 0.0


@dataclass
class Trace:
    run_id: str
    goal: str
    url: str
    steps: List[TraceStep] = field(default_factory=list)
    result: Optional[Any] = None
    success: bool = False
    total_steps: int = 0
    total_tokens: int = 0
    total_time_s: float = 0.0

    def add_step(self, step: TraceStep) -> None:
        self.steps.append(step)
        self.total_steps = len(self.steps)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "url": self.url,
            "steps": [
                {"step": s.step, "tool": s.tool, "args": s.args,
                 "success": s.success, "post_condition_met": s.post_condition_met,
                 "output": s.output, "error": s.error, "timestamp": s.timestamp}
                for s in self.steps
            ],
            "result": self.result,
            "success": self.success,
            "total_steps": self.total_steps,
            "total_tokens": self.total_tokens,
            "total_time_s": self.total_time_s,
        }


def record_trace(loop_result: Dict[str, Any], run_id: str, goal: str, url: str) -> Trace:
    """Convert a ChromeConnectLoop result into a Trace."""
    trace = Trace(run_id=run_id, goal=goal, url=url)
    for i, a in enumerate(loop_result.get("action_history", [])):
        trace.add_step(TraceStep(
            step=a.get("step", i + 1),
            tool=a.get("tool", ""),
            args=a.get("args", {}),
            success=a.get("success", False),
            post_condition_met=a.get("post_condition_met", False),
            output=None,
            error=a.get("error"),
            timestamp=time.time(),
        ))
    trace.result = loop_result.get("result")
    trace.success = loop_result.get("success", False)
    trace.total_steps = loop_result.get("steps", 0)
    trace.total_tokens = loop_result.get("tokens", 0)
    trace.total_time_s = loop_result.get("time_s", 0.0)
    return trace


# ---------------------------------------------------------------------------
# Adapter compiler
# ---------------------------------------------------------------------------

@dataclass
class CandidateAdapter:
    name: str
    version: str = "1.0.0"
    origin: str = ""
    task: str = ""
    selectors: Dict[str, str] = field(default_factory=dict)
    action_trace: List[Dict[str, Any]] = field(default_factory=list)
    expected_output: Optional[Dict[str, Any]] = None
    status: str = "proposed"  # proposed | approved | degraded
    created_at: str = ""
    compiled_from_run: str = ""
    fingerprint_map: Dict[str, str] = field(default_factory=dict)  # selector -> fingerprint

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "origin": self.origin,
            "task": self.task,
            "selectors": self.selectors,
            "action_trace": self.action_trace,
            "expected_output": self.expected_output,
            "status": self.status,
            "created_at": self.created_at,
            "compiled_from_run": self.compiled_from_run,
            "fingerprint_map": self.fingerprint_map,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CandidateAdapter":
        return cls(
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            origin=data.get("origin", ""),
            task=data.get("task", ""),
            selectors=data.get("selectors", {}),
            action_trace=data.get("action_trace", []),
            expected_output=data.get("expected_output"),
            status=data.get("status", "proposed"),
            created_at=data.get("created_at", ""),
            compiled_from_run=data.get("compiled_from_run", ""),
            fingerprint_map=data.get("fingerprint_map", {}),
        )


def compile_adapter(trace: Trace, name: str = "") -> Optional[CandidateAdapter]:
    """Compile a successful trace into a candidate adapter.

    Returns None if the trace was not successful.
    """
    if not trace.success:
        return None

    # Extract selectors from extract actions
    selectors: Dict[str, str] = {}
    expected_output: Optional[Dict[str, Any]] = None
    for step in trace.steps:
        if step.tool == "extract" and step.args.get("schema"):
            schema = step.args["schema"]
            for field_name in schema:
                selectors[field_name] = f"auto_{field_name}"  # placeholder selector
        if step.tool == "finish" and step.output:
            expected_output = step.output if isinstance(step.output, dict) else {"result": step.output}

    adapter_name = name or f"adapter_{trace.run_id[:8]}"
    adapter = CandidateAdapter(
        name=adapter_name,
        origin=trace.url.split("/")[2] if "/" in trace.url else trace.url,
        task=trace.goal,
        selectors=selectors,
        action_trace=[{"step": s.step, "tool": s.tool, "args": s.args} for s in trace.steps],
        expected_output=expected_output,
        status="proposed",
        created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        compiled_from_run=trace.run_id,
    )
    return adapter


def save_adapter(adapter: CandidateAdapter, adapter_dir: str = ADAPTER_DIR) -> str:
    """Save a candidate adapter to disk. Returns file path."""
    os.makedirs(adapter_dir, exist_ok=True)
    path = os.path.join(adapter_dir, f"{adapter.name}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(adapter.to_dict(), fh, indent=2, ensure_ascii=False)
    return path


def load_adapter(name: str, adapter_dir: str = ADAPTER_DIR) -> Optional[CandidateAdapter]:
    """Load an adapter by name."""
    path = os.path.join(adapter_dir, f"{name}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return CandidateAdapter.from_dict(data)


def list_adapters(adapter_dir: str = ADAPTER_DIR) -> List[str]:
    """List available adapter names."""
    if not os.path.exists(adapter_dir):
        return []
    return sorted(f.replace(".json", "") for f in os.listdir(adapter_dir) if f.endswith(".json"))


# ---------------------------------------------------------------------------
# Replay engine
# ---------------------------------------------------------------------------

def replay_adapter(
    adapter: CandidateAdapter,
    html_text: str,
    html_provider: Optional[Callable[[str], str]] = None,
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """Replay an adapter on new HTML. Returns (success, output, error_reason).

    Success = extracted fields match expected schema and non-empty.
    """
    if adapter.status == "degraded":
        return False, None, "adapter is degraded"

    # Extract using adapter's selectors
    elements = obs.extract_accessibility_tree(html_text)
    extracted: Dict[str, Any] = {}
    for field_name, selector in adapter.selectors.items():
        found = False
        # Strategy 1: match field name in element text
        for el in elements:
            text = el.get("text", "")
            if text and field_name.lower() in text.lower():
                extracted[field_name] = text
                found = True
                break
        # Strategy 2: match by tag (selector like "h1", "a", etc.)
        if not found:
            tag = selector.replace("auto_", "").replace("healed_", "").lower()
            # Strip common prefixes
            for prefix in ("healed_e", "auto_"):
                if tag.startswith(prefix):
                    tag = tag[len(prefix):]
            for el in elements:
                if el.get("tag", "").lower() == tag or el.get("role", "").lower() == tag:
                    extracted[field_name] = el.get("text", el.get("href", ""))
                    found = True
                    break
        # Strategy 3: first element with text
        if not found and elements:
            for el in elements:
                text = el.get("text", "")
                if text:
                    extracted[field_name] = text
                    found = True
                    break
        if not found:
            extracted[field_name] = None

    # Check: all fields non-None
    if any(v is None for v in extracted.values()):
        missing = [k for k, v in extracted.items() if v is None]
        return False, extracted, f"missing fields: {missing}"

    # Check: matches expected output shape
    if adapter.expected_output:
        for key in adapter.expected_output:
            if key not in extracted:
                return False, extracted, f"expected field '{key}' not in output"

    return True, extracted, None


# ---------------------------------------------------------------------------
# Local cache
# ---------------------------------------------------------------------------

def _cache_key(site: str, task: str, page_signature: str) -> str:
    raw = f"{site}|{task}|{page_signature}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def cache_get(site: str, task: str, page_signature: str) -> Optional[Dict[str, Any]]:
    """Get a cached result. Returns None on miss or expiry."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = _cache_key(site, task, page_signature)
    path = os.path.join(CACHE_DIR, f"{key}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        # Check TTL
        cached_at = data.get("_cached_at", 0)
        if time.time() - cached_at > CACHE_TTL_S:
            os.remove(path)
            return None
        return data.get("result")
    except (json.JSONDecodeError, OSError):
        return None


def cache_set(site: str, task: str, page_signature: str, result: Any) -> str:
    """Cache a result. Returns the cache key."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = _cache_key(site, task, page_signature)
    path = os.path.join(CACHE_DIR, f"{key}.json")
    data = {"_cached_at": time.time(), "key": key, "result": result}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    return key


def cache_clear() -> int:
    """Clear all cached results. Returns count removed."""
    if not os.path.exists(CACHE_DIR):
        return 0
    count = 0
    for f in os.listdir(CACHE_DIR):
        if f.endswith(".json"):
            os.remove(os.path.join(CACHE_DIR, f))
            count += 1
    return count


# ---------------------------------------------------------------------------
# Self-healer
# ---------------------------------------------------------------------------

def _fingerprint(el: Dict[str, Any]) -> str:
    parts = [el.get("tag", ""), el.get("role", ""), el.get("text", "")[:50]]
    return "|".join(parts)


def self_heal_selectors(
    adapter: CandidateAdapter,
    html_text: str,
) -> Tuple[bool, Optional[Dict[str, str]], Optional[str]]:
    """Try to relocate selectors via fingerprint similarity.

    Returns (healed, new_selectors, error_reason).
    """
    elements = obs.extract_accessibility_tree(html_text)
    if not elements:
        return False, None, "no elements in page"

    new_selectors: Dict[str, str] = {}
    healed = False

    for field_name, old_selector in adapter.selectors.items():
        # Try to find an element matching the field name
        found = False
        for el in elements:
            text = el.get("text", "")
            if field_name.lower() in text.lower() or field_name.lower() in el.get("name", "").lower():
                new_selectors[field_name] = f"healed_{el.get('ref', '')}"
                found = True
                healed = True
                break
        if not found:
            new_selectors[field_name] = old_selector  # keep old

    if not healed:
        return False, None, "no selectors could be relocated"

    return True, new_selectors, None


# ---------------------------------------------------------------------------
# Fallback orchestrator
# ---------------------------------------------------------------------------

def run_with_fallback(
    goal: str,
    url: str,
    html_provider: Callable[[str], str],
    adapter_name: Optional[str] = None,
    decision_fn: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Run adapter first; fall back to AI loop on failure.

    Returns {path: 'adapter'|'ai'|'failed', result, steps, time_s, ...}.
    """
    import chromeconnect_ai_loop as ail

    start = time.monotonic()

    # Try adapter
    if adapter_name:
        adapter = load_adapter(adapter_name)
        if adapter and adapter.status != "degraded":
            html_text = html_provider(url)
            page_sig = obs.snapshot_hash(html_text)
            # Check cache first
            cached = cache_get(url, goal, page_sig)
            if cached is not None:
                elapsed = time.monotonic() - start
                return {"path": "adapter_cached", "result": cached,
                        "steps": 0, "time_s": round(elapsed, 3), "cached": True}

            success, output, error = replay_adapter(adapter, html_text)
            if success:
                cache_set(url, goal, page_sig, output)
                elapsed = time.monotonic() - start
                return {"path": "adapter", "result": output, "steps": 0,
                        "time_s": round(elapsed, 3), "cached": False}

            # Try self-heal
            healed, new_selectors, heal_error = self_heal_selectors(adapter, html_text)
            if healed and new_selectors:
                adapter.selectors = new_selectors
                adapter.status = "degraded"  # mark for review
                save_adapter(adapter)
                success2, output2, error2 = replay_adapter(adapter, html_text)
                if success2:
                    cache_set(url, goal, page_sig, output2)
                    elapsed = time.monotonic() - start
                    return {"path": "adapter_healed", "result": output2, "steps": 0,
                            "time_s": round(elapsed, 3), "healed": True}

            # Adapter failed — fall through to AI
            adapter.status = "degraded"
            save_adapter(adapter)

    # AI fallback
    result = ail.run_loop(goal, html_provider, decision_fn)
    elapsed = time.monotonic() - start

    # If successful, compile candidate adapter
    if result.get("success"):
        trace = record_trace(result, f"run_{int(time.time())}", goal, url)
        candidate = compile_adapter(trace)
        if candidate:
            save_adapter(candidate)

    return {
        "path": "ai",
        "result": result.get("result"),
        "steps": result.get("steps", 0),
        "time_s": round(elapsed, 3),
        "gave_up_reason": result.get("gave_up_reason"),
        "success": result.get("success", False),
    }
