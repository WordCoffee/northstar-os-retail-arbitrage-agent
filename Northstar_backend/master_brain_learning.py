"""Master Brain Learning — learning loop + cache hierarchy (Phase A / A0).

Two coupled systems:

**Layer 1 — the learning loop (four signals).** Every edit/override/correction,
outcome, model-choice, and staleness event is captured as a structured record
(never a discarded diff) into ``learning/experience.jsonl`` (append-only). A
distillation pass compresses the raw stream into ``learning/playbooks.json``:
strategy templates with a confidence score and a TTL. Scores decay; entries
below threshold are dropped — the "unlearn" path. This converges toward the
"digital clone" principle (master plan §2.3).

**Layer 2 — the cache hierarchy (L0-L3).**

    L0 deterministic : exact intent signature + matching state hash -> replay output ($0)
    L1 playbook      : fingerprint match, confidence >= theta -> reuse plan on fresh data
    L2 fast-path     : similar-not-identical -> prompt-cached cheap model
    L3 frontier      : novelty / high stakes -> Tier-3

**Safety / constitution boundary.** Caching applies inside the Autonomous Zone
(planning, drafts, offline validation, replay). Live/paid steps are NEVER
auto-replayed: ``route_request(..., live=True)`` always returns L3 with
``requires_approval=True``. The circuit breaker still applies to replayed runs.

Pure and offline: no LLM call, no network call. Stdlib only.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# --- constants --------------------------------------------------------------

CACHE_TIERS = ("L0", "L1", "L2", "L3")
EXPERIENCE_KINDS = ("user_edit", "outcome", "model_choice", "staleness")

DEFAULT_CONFIDENCE_THRESHOLD = 0.60   # theta for L1 playbook replay
DEFAULT_TTL_SECONDS = 30 * 24 * 3600  # 30 days
DEFAULT_DECAY_PER_DAY = 0.02          # confidence lost per day without reinforcement
DEFAULT_PRIOR = 0.5                   # prior confidence before any outcome
OUTCOME_WEIGHT = {"accepted": 1.0, "partial": 0.5, "rejected": 0.0}

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(_REPO_ROOT, "00_STATE.json")


def learning_dir() -> str:
    """Learning artifacts directory (override with NORTHSTAR_LEARNING_DIR)."""
    return os.environ.get("NORTHSTAR_LEARNING_DIR") or os.path.join(_REPO_ROOT, "learning")


def experience_path() -> str:
    return os.path.join(learning_dir(), "experience.jsonl")


def playbooks_path() -> str:
    return os.path.join(learning_dir(), "playbooks.json")


def l0_cache_path() -> str:
    return os.path.join(learning_dir(), "l0_cache.json")


# --- canonicalization helpers ----------------------------------------------

def _canonical(obj: Any) -> str:
    """Stable, compact JSON for hashing (mirrors proof_batch_run.preflight_fingerprint)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _utc(now: Optional[datetime] = None) -> datetime:
    return now or datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def normalize_task(task: str) -> str:
    """Lowercase, collapse whitespace, strip trailing punctuation — no semantics lost."""
    if not isinstance(task, str):
        return ""
    text = " ".join(task.strip().split()).lower()
    return text.rstrip(".!?,;:")


def _classify(task: str) -> str:
    """Classify via the master-brain gateway (rules-based, offline)."""
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from master_brain_gateway import classify_task
        return classify_task(task)
    except Exception:
        return "AUTOTHINK_RESEARCH"


# --- Layer 1: intent signature ----------------------------------------------

def intent_signature(
    task: str,
    account_id: str = "default",
    task_class: Optional[str] = None,
) -> str:
    """Canonical, collision-resistant signature for a user intent.

    Combines the task class + normalized task + account partition, hashed with
    sha256. This is the L0/L1 cache key and the learning-loop grouping key.
    """
    canonical = {
        "task_class": task_class or _classify(task),
        "task": normalize_task(task),
        "account_id": account_id or "default",
    }
    return _sha256(_canonical(canonical))


# --- Layer 1: staleness / invalidation root ---------------------------------

def _state_invalidation_subset(state: Dict[str, Any]) -> Dict[str, Any]:
    """The stable subset of 00_STATE.json used as the invalidation key."""
    git = state.get("git_baseline", {}) or {}
    engine = state.get("engine", {}) or {}
    tb = state.get("test_baseline", {}) or {}
    issues = state.get("known_issues", []) or []
    return {
        "commit_hash": git.get("commit_hash"),
        "engine_primary_id": engine.get("primary_id"),
        "known_issue_status": sorted(
            f"{i.get('id')}:{i.get('status')}" for i in issues if isinstance(i, dict)
        ),
        "test_baseline_updated_at": tb.get("updated_at"),
    }


def state_hash(state_path: Optional[str] = None, profile_id: Optional[str] = None) -> str:
    """Composite invalidation key from 00_STATE.json (+ optional profile sha256)."""
    path = state_path or STATE_PATH
    state: Dict[str, Any] = {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, json.JSONDecodeError):
        state = {}
    subset = _state_invalidation_subset(state)
    subset["profile_sha256"] = _profile_sha256(profile_id) if profile_id else None
    return _sha256(_canonical(subset))


def _profile_sha256(profile_id: Optional[str]) -> Optional[str]:
    """Best-effort profile hash; None if the profile loader is unavailable."""
    if not profile_id:
        return None
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from master_brain_profiles import load_profile
        loaded = load_profile(profile_id)
        return loaded.get("sha256")
    except Exception:
        return None


# --- Layer 1: signal capture (append-only) ----------------------------------

def record_experience(
    kind: str,
    task: str,
    account_id: str = "default",
    task_class: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    path: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Append one structured learning signal to experience.jsonl. Never overwrites."""
    if kind not in EXPERIENCE_KINDS:
        raise ValueError(f"Invalid kind: {kind}. Must be one of {EXPERIENCE_KINDS}")

    sig = intent_signature(task, account_id=account_id, task_class=task_class)
    record = {
        "timestamp": _iso(_utc(now)),
        "kind": kind,
        "task": task,
        "task_class": task_class or _classify(task),
        "intent_signature": sig,
        "account_id": account_id or "default",
        "payload": payload or {},
    }

    out_path = path or experience_path()
    parent = os.path.dirname(out_path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(out_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def record_user_edit(
    task: str, field_name: str, before: Any, after: Any,
    account_id: str = "default", path: Optional[str] = None, now=None,
) -> Dict[str, Any]:
    """Signal 1 — the user changed X->Y on task T."""
    return record_experience(
        "user_edit", task, account_id=account_id, path=path, now=now,
        payload={"field": field_name, "from": before, "to": after},
    )


def record_outcome(
    task: str, outcome: str, detail: Optional[Dict[str, Any]] = None,
    account_id: str = "default", path: Optional[str] = None, now=None,
) -> Dict[str, Any]:
    """Signal 2 — did the run work? outcome in {accepted, partial, rejected}."""
    if outcome not in OUTCOME_WEIGHT:
        raise ValueError(f"Invalid outcome: {outcome}. Must be one of {tuple(OUTCOME_WEIGHT)}")
    return record_experience(
        "outcome", task, account_id=account_id, path=path, now=now,
        payload={"outcome": outcome, "detail": detail or {}},
    )


def record_model_choice(
    task: str, tier: str, model: str, latency_ms: Optional[float] = None,
    cost_usd: Optional[float] = None, ok: bool = True,
    account_id: str = "default", path: Optional[str] = None, now=None,
) -> Dict[str, Any]:
    """Signal 3 — which tier handled which task class, at what latency/cost/error."""
    return record_experience(
        "model_choice", task, account_id=account_id, path=path, now=now,
        payload={"tier": tier, "model": model, "latency_ms": latency_ms,
                 "cost_usd": cost_usd, "ok": ok},
    )


def record_staleness(
    task: str, reason: str, account_id: str = "default",
    path: Optional[str] = None, now=None,
) -> Dict[str, Any]:
    """Signal 4 — the state/config changed; anything keyed to the old state is stale."""
    return record_experience(
        "staleness", task, account_id=account_id, path=path, now=now,
        payload={"reason": reason, "state_hash": state_hash()},
    )


def read_experience(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Read all learning signals (oldest first). Skips corrupt lines. Missing -> []."""
    src = path or experience_path()
    if not os.path.exists(src):
        return []
    out: List[Dict[str, Any]] = []
    with open(src, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


# --- Layer 1: distillation -> playbooks -------------------------------------

def _confidence_for(events: List[Dict[str, Any]], prior: float = DEFAULT_PRIOR) -> float:
    """Confidence from outcome signals, pulled toward the prior when data is thin."""
    outcomes = [
        e.get("payload", {}).get("outcome")
        for e in events if e.get("kind") == "outcome"
    ]
    if not outcomes:
        return round(prior, 4)
    vals = [OUTCOME_WEIGHT[o] for o in outcomes if o in OUTCOME_WEIGHT]
    if not vals:
        return round(prior, 4)
    observed = sum(vals) / len(vals)
    # Weight observations against a small prior so a single sample can't dominate.
    n = len(vals)
    blended = (observed * n + prior * 2.0) / (n + 2.0)
    return round(blended, 4)


def _strategy_for(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Derive a reusable strategy: latest model choice + accumulated user edits."""
    model_choices = [e for e in events if e.get("kind") == "model_choice"]
    edits = [e for e in events if e.get("kind") == "user_edit"]
    strategy: Dict[str, Any] = {
        "model_choice": model_choices[-1]["payload"] if model_choices else None,
        "edits": [
            {"field": e["payload"].get("field"), "to": e["payload"].get("to")}
            for e in edits
        ][-10:],
    }
    return strategy


def distill(
    account_id: Optional[str] = None,
    path: Optional[str] = None,
    out_path: Optional[str] = None,
    now: Optional[datetime] = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> Dict[str, Any]:
    """Compress experience.jsonl into playbooks.json (strategy + confidence + TTL).

    Groups signals by intent signature, computes confidence from outcomes,
    and stamps the current state hash + expiry. Existing playbook hit counts
    and creation timestamps are preserved across distillation passes.
    """
    now_dt = _utc(now)
    events = read_experience(path)
    if account_id:
        events = [e for e in events if e.get("account_id") == account_id]

    existing = load_playbooks(out_path)
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for e in events:
        sig = e.get("intent_signature")
        if sig:
            groups.setdefault(sig, []).append(e)

    playbooks: Dict[str, Any] = {}
    for sig, evs in groups.items():
        prev = existing.get(sig, {})
        confidence = _confidence_for(evs)
        playbooks[sig] = {
            "intent_signature": sig,
            "task_class": evs[-1].get("task_class"),
            "task": evs[-1].get("task"),
            "account_id": evs[-1].get("account_id", "default"),
            "strategy": _strategy_for(evs),
            "confidence": confidence,
            "observations": len(evs),
            "state_hash": state_hash(),
            "hits": int(prev.get("hits", 0)),
            "created_at": prev.get("created_at", _iso(now_dt)),
            "updated_at": _iso(now_dt),
            "expires_at": _iso(now_dt + timedelta(seconds=ttl_seconds)),
            "ttl_seconds": ttl_seconds,
        }

    # Preserve any existing playbooks not re-derived (e.g. manually curated).
    for sig, pb in existing.items():
        playbooks.setdefault(sig, pb)

    dst = out_path or playbooks_path()
    _atomic_write_json(dst, playbooks)
    return playbooks


def load_playbooks(out_path: Optional[str] = None) -> Dict[str, Any]:
    """Load the distilled playbook store. Missing/corrupt -> {}."""
    src = out_path or playbooks_path()
    if not os.path.exists(src):
        return {}
    try:
        with open(src, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def get_playbook(
    sig: str, account_id: str = "default",
    min_confidence: float = DEFAULT_CONFIDENCE_THRESHOLD,
    out_path: Optional[str] = None, now: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """Return a playbook if it matches intent + account, clears theta, and isn't expired."""
    pb = load_playbooks(out_path).get(sig)
    if not pb:
        return None
    if pb.get("account_id") != (account_id or "default"):
        return None
    if float(pb.get("confidence", 0.0)) < min_confidence:
        return None
    exp = pb.get("expires_at")
    if exp:
        try:
            if _utc(now) > datetime.fromisoformat(exp):
                return None
        except ValueError:
            pass
    return pb


# --- Layer 1: decay + unlearn -----------------------------------------------

def decay_and_prune(
    out_path: Optional[str] = None, now: Optional[datetime] = None,
    per_day: float = DEFAULT_DECAY_PER_DAY,
    floor: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> Dict[str, Any]:
    """Age confidence down; drop entries that fall below the floor or expire."""
    now_dt = _utc(now)
    playbooks = load_playbooks(out_path)
    kept: Dict[str, Any] = {}
    dropped: List[str] = []
    for sig, pb in playbooks.items():
        last = pb.get("updated_at")
        days = 0.0
        if last:
            try:
                days = max(0.0, (now_dt - datetime.fromisoformat(last)).total_seconds() / 86400.0)
            except ValueError:
                days = 0.0
        conf = max(0.0, float(pb.get("confidence", 0.0)) - per_day * days)
        pb["confidence"] = round(conf, 4)
        expired = False
        exp = pb.get("expires_at")
        if exp:
            try:
                expired = now_dt > datetime.fromisoformat(exp)
            except ValueError:
                expired = False
        if conf < floor or expired:
            dropped.append(sig)
        else:
            kept[sig] = pb
    _atomic_write_json(out_path or playbooks_path(), kept)
    return {"kept": len(kept), "dropped": dropped}


def unlearn_topic(
    topic: str, account_id: str = "default", out_path: Optional[str] = None,
) -> List[str]:
    """Unlearn every playbook whose task/strategy matches a topic substring."""
    needle = normalize_task(topic)
    playbooks = load_playbooks(out_path)
    removed: List[str] = []
    for sig, pb in list(playbooks.items()):
        if account_id and pb.get("account_id") != account_id:
            continue
        haystack = normalize_task(str(pb.get("task", "")) + " " + _canonical(pb.get("strategy", {})))
        if needle and needle in haystack:
            removed.append(sig)
            playbooks.pop(sig, None)
    _atomic_write_json(out_path or playbooks_path(), playbooks)
    return removed


def unlearn_intent(sig: str, out_path: Optional[str] = None) -> bool:
    """Unlearn a single playbook by exact intent signature."""
    playbooks = load_playbooks(out_path)
    if sig in playbooks:
        playbooks.pop(sig)
        _atomic_write_json(out_path or playbooks_path(), playbooks)
        return True
    return False


# --- Layer 2: cache hierarchy + routing -------------------------------------

@dataclass
class RouteDecision:
    """Outcome of a routing request (tier + action + safety)."""
    tier: str
    action: str                 # replay | replay_plan | generate | escalate | approval_required
    fingerprint: str
    intent_signature: str
    state_hash: str
    requires_approval: bool
    reason: str
    model_hint: Optional[str] = None
    playbook: Optional[Dict[str, Any]] = None


def fingerprint(
    task: str, account_id: str = "default",
    state_path: Optional[str] = None, profile_id: Optional[str] = None,
) -> Dict[str, str]:
    """Combined key: intent signature + state hash -> fingerprint."""
    sig = intent_signature(task, account_id=account_id)
    sh = state_hash(state_path=state_path, profile_id=profile_id)
    return {
        "intent_signature": sig,
        "state_hash": sh,
        "fingerprint": _sha256(f"{sig}:{sh}"),
    }


def _load_l0(path: Optional[str] = None) -> Dict[str, Any]:
    src = path or l0_cache_path()
    if not os.path.exists(src):
        return {}
    try:
        with open(src, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def cache_get(fp: str, path: Optional[str] = None, now: Optional[datetime] = None) -> Optional[Any]:
    """L0 deterministic lookup by exact fingerprint (honours TTL)."""
    entry = _load_l0(path).get(fp)
    if not entry:
        return None
    exp = entry.get("expires_at")
    if exp:
        try:
            if _utc(now) > datetime.fromisoformat(exp):
                return None
        except ValueError:
            pass
    return entry.get("output")


def cache_put(
    fp: str, output: Any, ttl_seconds: int = DEFAULT_TTL_SECONDS,
    path: Optional[str] = None, now: Optional[datetime] = None,
) -> None:
    """Store an L0 deterministic entry (exact-fingerprint replay)."""
    store = _load_l0(path)
    now_dt = _utc(now)
    store[fp] = {
        "output": output,
        "created_at": _iso(now_dt),
        "expires_at": _iso(now_dt + timedelta(seconds=ttl_seconds)),
        "ttl_seconds": ttl_seconds,
    }
    _atomic_write_json(path or l0_cache_path(), store)


_LIVE_MARKERS = (
    "live", "purchase", "buy", "publish", "deploy", "charge", "spend",
    "send", "post", "submit", "execute live", "place order",
)


def is_live_gated(task: str, live: bool = False) -> bool:
    """True when a request must NOT be auto-replayed (live/paid/constitution §3)."""
    if live:
        return True
    text = normalize_task(task)
    return any(m in text for m in _LIVE_MARKERS)


def route_request(
    task: str,
    account_id: str = "default",
    live: bool = False,
    state_path: Optional[str] = None,
    profile_id: Optional[str] = None,
    l0_path: Optional[str] = None,
    playbooks_path: Optional[str] = None,
    min_confidence: float = DEFAULT_CONFIDENCE_THRESHOLD,
    now: Optional[datetime] = None,
) -> RouteDecision:
    """Route a request through L0 -> L1 -> L2 -> L3.

    Live/paid requests are never auto-replayed: they always return L3 with
    ``requires_approval=True`` (execution still needs a fresh named approval).
    """
    fp = fingerprint(task, account_id=account_id, state_path=state_path, profile_id=profile_id)
    sig, sh, fpv = fp["intent_signature"], fp["state_hash"], fp["fingerprint"]

    if is_live_gated(task, live=live):
        return RouteDecision(
            tier="L3", action="approval_required", fingerprint=fpv,
            intent_signature=sig, state_hash=sh, requires_approval=True,
            reason="live/paid task — replay forbidden (constitution §3)",
        )

    cached = cache_get(fpv, path=l0_path, now=now)
    if cached is not None:
        return RouteDecision(
            tier="L0", action="replay", fingerprint=fpv, intent_signature=sig,
            state_hash=sh, requires_approval=False, reason="exact fingerprint + state hash match",
        )

    pb = get_playbook(sig, account_id=account_id, min_confidence=min_confidence,
                      out_path=playbooks_path, now=now)
    if pb:
        return RouteDecision(
            tier="L1", action="replay_plan", fingerprint=fpv, intent_signature=sig,
            state_hash=sh, requires_approval=False,
            reason=f"playbook confidence {pb.get('confidence')} >= {min_confidence}",
            playbook=pb,
        )

    # L2 fast-path: a similar (lower-confidence) playbook exists -> use as few-shot.
    lower = get_playbook(sig, account_id=account_id, min_confidence=0.0,
                         out_path=playbooks_path, now=now)
    if lower:
        return RouteDecision(
            tier="L2", action="generate", fingerprint=fpv, intent_signature=sig,
            state_hash=sh, requires_approval=False,
            model_hint="fast-path (prompt-cached)", reason="similar playbook available as few-shot",
            playbook=lower,
        )

    return RouteDecision(
        tier="L3", action="escalate", fingerprint=fpv, intent_signature=sig,
        state_hash=sh, requires_approval=False, reason="novelty — no playbook or cache hit",
        model_hint="frontier",
    )


# --- io helpers -------------------------------------------------------------

def _atomic_write_json(path: str, data: Any) -> None:
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, path)
