"""D16 - Model Scout lane.

Keeps one fixed eval set per local role, measures candidates against the
incumbent, and *recommends* a swap. It never swaps anything on its own: a
replacement is written to ``ty/model_leaderboard.json`` as a recommendation with
a quarantine tag and a tested restore plan.

    # plan only: no GPU, no network, no model load
    python tools/model_scout.py --plan

    # the GPU run the Director executes (one model resident at a time)
    python tools/model_scout.py --run --role bojo-router \
        --models qwen3.5:4b,qwen3.5:2b,gemma3:4b,qwen2.5-coder:3b

    # show / apply the restore plan for a role
    python tools/model_scout.py --restore bojo-router

Rules this file enforces:
  * No download. A model that is not already installed is recorded as
    ``not_installed`` and skipped; nothing is pulled.
  * One resident model. It takes the GPU lock through ``tools/gpu_budget.py``,
    calls ``enforce(keep=[])`` before the run and unloads + waits between models.
    ``OLLAMA_MAX_LOADED_MODELS=1`` belongs to the Ollama server process; the
    runner records what the environment actually says instead of pretending it
    can change a running server.
  * Swap only on a clear margin. A candidate must beat the incumbent by at least
    ``SWAP_MARGIN_ITEMS`` correct items on the *same* eval set and fit the role's
    VRAM budget and the RAM floor. Otherwise the incumbent keeps the role.

Everything in the eval files is data. A reply that contains instructions is
scored as text and never executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = Path(__file__).resolve().parent / "model_scout" / "evals"
ROLES_PATH = ROOT / "ty" / "model_roles.json"
LEADERBOARD_PATH = ROOT / "ty" / "model_leaderboard.json"
INTEL_MIRROR_PATH = ROOT / "state" / "intel" / "models.json"

#: Mirrors tools/gpu_budget.py. Kept local so scoring stays pure and testable,
#: and asserted equal in test_model_scout.py::test_budget_constants_match_manager.
ROLE_BUDGET_GB = {
    "bojo": 3.5,
    "router": 3.5,
    "coder": 7.0,
    "vision": 8.0,
    "gui_grounding": 8.0,
    "embeddings": 2.5,
    "image_flux": 11.0,
    "image_t2i": 11.0,
    "27b": 14.5,
}
RESERVE_GB = 1.0
RAM_FLOOR_GB = 2.0
TOTAL_VRAM_GB = 16.0

#: Correct items a candidate must gain before it may replace an incumbent.
SWAP_MARGIN_ITEMS = 2

LANE_ALIASES = {
    "bojo": "bojo", "router": "bojo", "assistant": "bojo", "general": "bojo",
    "coder": "coder", "code": "coder", "coding": "coder",
    "planner": "coder", "planner-coder": "coder", "planner_coder": "coder",
    "vision": "vision", "vlm": "vision", "screenshot": "vision",
    "gui_grounding": "gui_grounding", "gui-grounding": "gui_grounding",
    "gui": "gui_grounding", "grounding": "gui_grounding", "ui_automation": "gui_grounding",
    "embeddings": "embeddings", "embedding": "embeddings",
    "memory": "embeddings", "recall": "embeddings",
    "image": "image", "images": "image", "image-gen": "image",
    "render": "image", "diffusion": "image", "comfyui": "image",
}


# ---------------------------------------------------------------- eval loading
def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


EVAL_FILES = {"router": "router_18.json", "json_adherence": "json_adherence_10.json"}


def eval_path(name: str) -> Path:
    """Eval files keep their item count in the name so a length change is visible."""
    return EVAL_DIR / EVAL_FILES.get(name, f"{name}.json")


def load_eval(name: str) -> Dict[str, Any]:
    """Load and validate one eval set. A malformed set is an error, not a zero."""
    path = eval_path(name)
    data = _read_json(path)
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"{path}: no cases")
    ids = [case.get("id") for case in cases]
    if len(set(ids)) != len(ids) or None in ids:
        raise ValueError(f"{path}: item ids must be unique and present")
    declared = data.get("items")
    if declared is not None and declared != len(cases):
        raise ValueError(f"{path}: declares {declared} items but holds {len(cases)}")
    if name == "router":
        lanes = data.get("lane_definitions") or {}
        for case in cases:
            if case.get("expect") not in lanes:
                raise ValueError(f"{path}: {case.get('id')} expects unknown lane {case.get('expect')!r}")
    if name == "json_adherence":
        for case in cases:
            if not isinstance(case.get("schema"), dict):
                raise ValueError(f"{path}: {case.get('id')} has no schema")
    return {"name": name, "path": str(path.relative_to(ROOT)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "cases": cases, **{k: v for k, v in data.items() if k != "cases"}}


def available_evals() -> List[str]:
    return sorted(name for name in EVAL_FILES if eval_path(name).is_file())


# ---------------------------------------------------------------- json helpers
def extract_json(reply: str) -> Tuple[Any, bool, str]:
    """Return (value, strict, note).

    strict=True only when the reply is exactly one JSON value, optionally inside
    a single ``` fence. Prose around a valid object is not strict: the whole
    point of the adherence eval is the no-prose contract.
    """
    text = (reply or "").strip()
    if not text:
        return None, False, "empty"
    fenced = text
    if fenced.startswith("```"):
        first_newline = fenced.find("\n")
        if first_newline == -1:
            return None, False, "unterminated fence"
        fenced = fenced[first_newline + 1:]
        if fenced.rstrip().endswith("```"):
            fenced = fenced.rstrip()[:-3]
        text = fenced.strip()
    try:
        return json.loads(text), True, "ok"
    except ValueError:
        pass
    start = text.find("{") if text.find("{") != -1 else text.find("[")
    if start == -1:
        return None, False, "no json value"
    for end in range(len(text), start, -1):
        try:
            return json.loads(text[start:end]), False, "json buried in prose"
        except ValueError:
            continue
    return None, False, "unparsable json"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate(value: Any, schema: Dict[str, Any], path: str = "$") -> List[str]:
    """Small declarative validator: type, enum, required, properties, items."""
    problems: List[str] = []
    kind = schema.get("type")
    type_ok = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "number": _is_number(value),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }
    if kind and not type_ok.get(kind, True):
        return [f"{path}: expected {kind}, got {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        problems.append(f"{path}: {value!r} not in {schema['enum']!r}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                problems.append(f"{path}.{key}: missing")
        properties = schema.get("properties") or {}
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    problems.append(f"{path}.{key}: not allowed")
        for key, sub in properties.items():
            if key in value:
                problems.extend(validate(value[key], sub, f"{path}.{key}"))
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            problems.append(f"{path}: {len(value)} items < {schema['minItems']}")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            problems.append(f"{path}: {len(value)} items > {schema['maxItems']}")
        if isinstance(schema.get("items"), dict):
            for index, item in enumerate(value):
                problems.extend(validate(item, schema["items"], f"{path}[{index}]"))
    if _is_number(value):
        if "minimum" in schema and value < schema["minimum"]:
            problems.append(f"{path}: {value} below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            problems.append(f"{path}: {value} above maximum {schema['maximum']}")
    return problems


# ---------------------------------------------------------------- scoring
def parse_lane(reply: str) -> Optional[str]:
    """The lane a reply names. JSON ``{"lane": ...}`` wins over prose."""
    if not reply:
        return None
    value, _strict, _note = extract_json(reply)
    if isinstance(value, dict):
        named = value.get("lane") or value.get("route") or value.get("role")
        if isinstance(named, str):
            return LANE_ALIASES.get(named.strip().lower())
    lowered = reply.lower()
    best: Optional[Tuple[int, str]] = None
    for alias, lane in LANE_ALIASES.items():
        index = lowered.find(alias)
        if index == -1:
            continue
        before = lowered[index - 1] if index else " "
        after = lowered[index + len(alias)] if index + len(alias) < len(lowered) else " "
        if (before.isalnum() or before == "_") or (after.isalnum() or after == "_"):
            continue
        if best is None or index < best[0]:
            best = (index, lane)
    return best[1] if best else None


def score_router(cases: Sequence[Dict[str, Any]], replies: Sequence[str]) -> Dict[str, Any]:
    rows = []
    correct = 0
    for case, reply in zip(cases, replies):
        lane = parse_lane(reply)
        ok = lane == case["expect"]
        correct += int(ok)
        rows.append({"id": case["id"], "expect": case["expect"],
                     "matched": lane, "ok": ok})
    return {"correct": correct, "items": len(cases),
            "accuracy": round(correct / len(cases), 3) if cases else 0.0,
            "rows": rows}


def score_json(cases: Sequence[Dict[str, Any]], replies: Sequence[str]) -> Dict[str, Any]:
    rows = []
    correct = 0
    strict_count = 0
    for case, reply in zip(cases, replies):
        value, strict, note = extract_json(reply)
        strict_count += int(strict)
        problems = validate(value, case["schema"]) if value is not None else [note]
        ok = strict and not problems
        correct += int(ok)
        rows.append({"id": case["id"], "ok": ok, "strict": strict,
                     "note": note, "problems": problems[:4]})
    return {"correct": correct, "items": len(cases),
            "accuracy": round(correct / len(cases), 3) if cases else 0.0,
            "strict": strict_count, "rows": rows}


def score(eval_set: Dict[str, Any], replies: Sequence[str]) -> Dict[str, Any]:
    if len(replies) != len(eval_set["cases"]):
        raise ValueError(f"expected {len(eval_set['cases'])} replies, got {len(replies)}")
    if eval_set["name"] == "router":
        return score_router(eval_set["cases"], replies)
    if eval_set["name"] == "json_adherence":
        return score_json(eval_set["cases"], replies)
    raise ValueError(f"no scorer for eval {eval_set['name']!r}")


# ---------------------------------------------------------------- swap rule
def fit_check(role_budget_gb: Optional[float], vram_gb: Optional[float],
              ram_free_gb: Optional[float], *, reserve_gb: float = RESERVE_GB,
              ram_floor_gb: float = RAM_FLOOR_GB) -> Dict[str, Any]:
    """Does a measured model fit its role budget and the machine floors?"""
    if role_budget_gb is None:
        return {"ok": False, "reason": "no budget for role", "problems": ["unknown role budget"]}
    problems: List[str] = []
    if vram_gb is None:
        problems.append("VRAM not measured")
    elif vram_gb > role_budget_gb:
        problems.append(f"{vram_gb} GB VRAM > {role_budget_gb} GB role budget")
    if ram_free_gb is None:
        problems.append("free RAM not measured")
    elif ram_free_gb < ram_floor_gb:
        problems.append(f"{ram_free_gb} GB RAM free < {ram_floor_gb} GB floor")
    return {"ok": not problems, "problems": problems,
            "budget_gb": role_budget_gb, "vram_gb": vram_gb,
            "ram_free_gb": ram_free_gb, "reserve_gb": reserve_gb}


def decide(incumbent_correct: Optional[int], candidate_correct: Optional[int],
           items: int, fit: Dict[str, Any], *,
           margin: int = SWAP_MARGIN_ITEMS) -> Dict[str, Any]:
    """The whole swap rule in one pure function. Nothing swaps by itself."""
    if incumbent_correct is None:
        return {"verdict": "hold", "reason": "incumbent not measured on this eval set",
                "delta": None, "required_margin": margin, "fits": fit}
    if candidate_correct is None:
        return {"verdict": "hold", "reason": "candidate not measured",
                "delta": None, "required_margin": margin, "fits": fit}
    delta = candidate_correct - incumbent_correct
    if delta < margin:
        return {"verdict": "keep-incumbent",
                "reason": f"margin {delta:+d} < required +{margin}",
                "delta": delta, "required_margin": margin, "fits": fit}
    if not fit.get("ok"):
        return {"verdict": "keep-incumbent",
                "reason": "beats the margin but does not fit: " + "; ".join(fit.get("problems") or []),
                "delta": delta, "required_margin": margin, "fits": fit}
    return {"verdict": "replace",
            "reason": f"margin {delta:+d} >= +{margin} and fits {fit.get('budget_gb')} GB",
            "delta": delta, "required_margin": margin, "fits": fit}


def recommend(role_entry: Dict[str, Any], measurements: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Pick at most one replacement for a role from measured candidates."""
    incumbent = role_entry.get("incumbent")
    eval_name = role_entry.get("eval")
    items = (measurements.get(incumbent or "", {}).get("items")
             or next((row.get("items") for row in measurements.values() if row.get("items")), 0))
    budget = role_entry.get("budget_gb")
    base = measurements.get(incumbent or "") if incumbent else None
    incumbent_correct = (base or {}).get("correct") if base and base.get("status") == "measured" else None
    considered = []
    winner: Optional[Dict[str, Any]] = None
    for model, result in measurements.items():
        if model == incumbent:
            continue
        if result.get("status") != "measured":
            considered.append({"model": model, "verdict": "hold",
                               "reason": f"not measured: {result.get('status')}"})
            continue
        fit = fit_check(budget, result.get("vram_gb"), result.get("ram_free_gb"))
        decision = decide(incumbent_correct, result.get("correct"), items, fit)
        considered.append({"model": model, **decision})
        if decision["verdict"] == "replace":
            if winner is None or (result.get("correct") or 0) > (winner["correct"] or 0):
                winner = {"model": model, **result, "decision": decision}
    if winner:
        return {"verdict": "replace", "incumbent": incumbent, "model": winner["model"],
                "reason": winner["decision"]["reason"], "eval": eval_name,
                "candidates": considered, "winner_correct": winner.get("correct")}
    return {"verdict": "keep-incumbent", "incumbent": incumbent, "model": incumbent,
            "reason": "no candidate cleared the margin and the budget",
            "eval": eval_name, "candidates": considered}


# ---------------------------------------------------------------- plans
def _stamp(now: Optional[datetime] = None) -> str:
    return (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")


def quarantine_plan(incumbent: str, *, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Copy, never move: the old tag stays resolvable and the copy is the marker."""
    base = incumbent.split(":", 1)[0]
    tag = f"{base}:quarantine-{_stamp(now)}"
    return {"from": incumbent, "tag": tag, "delete_original": False,
            "commands": [f"ollama cp {incumbent} {tag}", f"ollama show {tag}"]}


def restore_plan(role: str, leaderboard: Dict[str, Any]) -> Dict[str, Any]:
    """A tested plan, not a model move. ``--apply`` runs exactly these commands."""
    entry = (leaderboard.get("roles") or {}).get(role)
    if not entry:
        raise KeyError(f"unknown role {role!r}")
    incumbent = entry.get("incumbent")
    quarantine = (entry.get("quarantine") or {})
    tag = quarantine.get("tag")
    manager_key = entry.get("manager_key")
    commands: List[str] = []
    if tag:
        commands.append(f"ollama cp {tag} {incumbent}")
    commands.append(f"ollama show {incumbent}")
    return {"role": role, "model": incumbent, "quarantine_tag": tag,
            "commands": commands, "apply": False, "dry_run": True,
            "manager_key": manager_key,
            "repoint": (f"ROLE_MODELS[{manager_key!r}] = {incumbent!r}"
                        if manager_key else "no ROLE_MODELS entry: this role is not an Ollama tag"),
            "note": "Restores the recorded incumbent tag. It does not delete the candidate."}


# ---------------------------------------------------------------- leaderboard
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_leaderboard(roles: Dict[str, Any], measurements: Optional[Dict[str, Dict[str, Any]]] = None,
                      *, generated_at: Optional[str] = None) -> Dict[str, Any]:
    measurements = measurements or {}
    out: Dict[str, Any] = {
        "schema": 1,
        "generated_at": generated_at or _now(),
        "generated_by": "tools/model_scout.py",
        "swap_rule": {"margin_items": SWAP_MARGIN_ITEMS,
                      "must_fit": "role VRAM budget and the 2.0 GB RAM floor",
                      "auto_swap": False},
        "eval_sets": {},
        "roles": {},
    }
    for name in sorted({entry.get("eval") for entry in roles.values() if entry.get("eval")}):
        try:
            loaded = load_eval(name)
        except (OSError, ValueError) as exc:
            out["eval_sets"][name] = {"path": str(eval_path(name)), "error": str(exc)}
            continue
        out["eval_sets"][name] = {"path": loaded["path"], "sha256": loaded["sha256"],
                                  "items": len(loaded["cases"])}
    for role, entry in roles.items():
        measured = {model: row for model, row in measurements.items()
                    if row.get("role") == role}
        out["roles"][role] = {
            "label": entry.get("label"),
            "lane": entry.get("lane"),
            "eval": entry.get("eval"),
            "budget_key": entry.get("budget_key"),
            "budget_gb": entry.get("budget_gb"),
            "manager_key": entry.get("manager_key"),
            "incumbent": entry.get("incumbent"),
            "baseline": entry.get("baseline"),
            "candidates": entry.get("candidates") or [],
            "quarantined": entry.get("quarantined") or [],
            "measurements": measured,
            "recommendation": recommend(entry, measured) if measured else {
                "verdict": "unmeasured", "incumbent": entry.get("incumbent"),
                "model": entry.get("incumbent"), "eval": entry.get("eval"),
                "reason": "no --run measurement in this leaderboard yet"},
            "quarantine": None,
            "notes": entry.get("notes"),
        }
        rec = out["roles"][role]["recommendation"]
        if rec.get("verdict") == "replace" and entry.get("incumbent"):
            out["roles"][role]["quarantine"] = quarantine_plan(entry["incumbent"])
    return out


def _display_path(path: Path) -> str:
    """Repository-relative when possible, absolute otherwise (tests use temp dirs)."""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def write_leaderboard(leaderboard: Dict[str, Any], *,
                      path: Path = LEADERBOARD_PATH,
                      mirror: Optional[Path] = INTEL_MIRROR_PATH) -> Dict[str, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(leaderboard, indent=2) + "\n", encoding="utf-8")
    written = {"leaderboard": str(path)}
    if mirror is not None:
        mirror.parent.mkdir(parents=True, exist_ok=True)
        mirror_payload = {"schema": 1,
                          "source": _display_path(path),
                          "generated_at": leaderboard.get("generated_at"),
                          "swap_rule": leaderboard.get("swap_rule"),
                          "roles": {
                              role: {
                                  "incumbent": row.get("incumbent"),
                                  "eval": row.get("eval"),
                                  "recommendation": row.get("recommendation"),
                                  "candidates": [
                                      {"model": model,
                                       "status": value.get("status"),
                                       "correct": value.get("correct"),
                                       "items": value.get("items"),
                                       "latency_ms": value.get("latency_ms"),
                                       "vram_gb": value.get("vram_gb"),
                                       "ram_free_gb": value.get("ram_free_gb")}
                                      for model, value in (row.get("measurements") or {}).items()
                                  ],
                              }
                              for role, row in (leaderboard.get("roles") or {}).items()
                          }}
        mirror.write_text(json.dumps(mirror_payload, indent=2) + "\n", encoding="utf-8")
        written["mirror"] = str(mirror)
    return written


def load_roles(path: Path = ROLES_PATH) -> Dict[str, Any]:
    return (_read_json(path) or {}).get("roles") or {}


# ---------------------------------------------------------------- ollama access
def base_url() -> str:
    raw = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").strip()
    if not raw.startswith("http"):
        raw = "http://" + raw
    return raw.rstrip("/")


def installed_models(timeout: float = 10.0) -> List[str]:
    with urllib.request.urlopen(base_url() + "/api/tags", timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace") or "{}")
    return [str(row.get("name")) for row in data.get("models") or []]


def _post(path: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    request = urllib.request.Request(
        base_url() + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace") or "{}")


def chat(model: str, system: str, user: str, *, num_predict: int = 80,
         timeout: float = 180.0) -> Tuple[str, float]:
    started = time.perf_counter()
    body = _post("/api/chat", {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "stream": False,
        # Qwen3.5-family models (qwen3.5:*, bojo:latest) think by default on this Ollama
        # build: the thinking goes to a separate `thinking` field and `content` comes back
        # EMPTY after num_predict tokens. Measured 2026-11-08: 300 tokens of thinking, ""
        # content, on every router item. With think=false the same model answers "coder".
        # A router eval that does not disable thinking measures the parser, not the model.
        "think": False,
        "options": {"temperature": 0, "num_predict": num_predict},
    }, timeout)
    reply = (body.get("message") or {}).get("content") or ""
    return reply, round(time.perf_counter() - started, 3)


def router_prompt(eval_set: Dict[str, Any]) -> str:
    lanes = "\n".join(f"- {name}: {text}" for name, text in eval_set["lane_definitions"].items())
    return ("You are the Northstar lane router. Reply with exactly one lane name and nothing else.\n"
            f"Lanes:\n{lanes}")


# ---------------------------------------------------------------- measurement
def _gpu_manager():
    """Import the GPU manager from tools/ without requiring a package import."""
    tools_dir = str(Path(__file__).resolve().parent)
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    import gpu_budget  # noqa: F401  (tools/gpu_budget.py)
    return gpu_budget


def measure_model(model: str, role: str, eval_set: Dict[str, Any], *,
                  num_predict: int = 80, timeout: float = 180.0,
                  gpu=None) -> Dict[str, Any]:
    """Load once, ask every item, unload. Never pulls, never retries."""
    gpu = gpu or _gpu_manager()
    system = eval_set.get("system") or router_prompt(eval_set)
    load = gpu.load(model, role=role)
    if not load.get("ok"):
        return {"model": model, "role": role, "status": "load_failed",
                "reason": load.get("reason") or "load refused",
                "problems": load.get("problems") or []}
    served: Dict[str, Any] = {}
    try:
        ps_rows = [row for row in gpu.ps() if row.get("name") == model]
        served = ps_rows[0] if ps_rows else {}
        replies: List[str] = []
        latencies: List[float] = []
        error: Optional[str] = None
        for case in eval_set["cases"]:
            instruction = case.get("instruction") or case.get("intent")
            try:
                reply, elapsed = chat(model, system, instruction,
                                      num_predict=num_predict, timeout=timeout)
            except (urllib.error.URLError, OSError, ValueError) as exc:
                error = f"{type(exc).__name__}: {exc}"
                break
            replies.append(reply)
            latencies.append(elapsed)
        if error:
            return {"model": model, "role": role, "status": "chat_failed",
                    "reason": error, "answered": len(replies)}
        scored = score(eval_set, replies)
        mem = gpu.ram()
        return {"model": model, "role": role, "status": "measured",
                "eval": eval_set["name"], **scored,
                "latency_ms": int(statistics.mean(latencies) * 1000) if latencies else None,
                "latency_p95_ms": int(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)] * 1000)
                if latencies else None,
                "vram_gb": served.get("size_vram_gb"),
                "size_gb": served.get("size_gb"),
                "processor": served.get("processor"),
                "ram_free_gb": mem.get("free_gb"),
                "replies": replies}
    finally:
        gpu.unload(model)
        gpu.wait_until_unloaded()


def run(args: argparse.Namespace) -> int:
    roles = load_roles()
    role = args.role
    if role not in roles:
        print(f"error: unknown role {role!r}; known: {', '.join(sorted(roles))}", file=sys.stderr)
        return 2
    entry = roles[role]
    eval_name = entry.get("eval")
    if not eval_name:
        print(f"error: role {role!r} has no eval set; scouting it would be an opinion, not a measurement",
              file=sys.stderr)
        return 2
    eval_set = load_eval(eval_name)

    requested = [m.strip() for m in (args.models or "").split(",") if m.strip()]
    models: List[str] = []
    for model in ([entry.get("incumbent")] if entry.get("incumbent") and not args.no_incumbent else []) + requested:
        if model and model not in models:
            models.append(model)
    if not models:
        print("error: --run needs at least one model (or an incumbent on the role)", file=sys.stderr)
        return 2

    try:
        installed = set(installed_models())
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"error: Ollama unreachable at {base_url()}: {exc}", file=sys.stderr)
        return 2

    gpu = _gpu_manager()
    env_pin = os.environ.get("OLLAMA_MAX_LOADED_MODELS", "")
    print(json.dumps({"event": "run_start", "role": role, "eval": eval_name,
                      "models": models, "installed": sorted(installed),
                      "ollama_max_loaded_models_env": env_pin or "unset",
                      "note": "the pin belongs to the server process; this runner enforces one "
                              "resident model by unloading between models"}, indent=2))
    lock = gpu.lock(f"model_scout:{role}", ttl_s=args.lock_ttl_s)
    if not lock.get("ok"):
        print(f"error: GPU locked by {lock.get('held_by')}", file=sys.stderr)
        return 3
    measurements: Dict[str, Dict[str, Any]] = {}
    try:
        gpu.enforce(keep=[])
        for model in models:
            if model not in installed:
                measurements[model] = {"model": model, "role": role, "status": "not_installed",
                                       "reason": "not in /api/tags; the scout never pulls"}
                print(json.dumps(measurements[model]), flush=True)
                continue
            result = measure_model(model, role, eval_set, num_predict=args.num_predict,
                                   timeout=args.timeout, gpu=gpu)
            measurements[model] = result
            print(json.dumps({key: value for key, value in result.items() if key != "replies"}),
                  flush=True)
    finally:
        for model in models:
            gpu.unload(model)
        gpu.unlock(role)
        print(json.dumps({"event": "run_end", "gpu": gpu.snapshot()}, indent=2))

    leaderboard = build_leaderboard(roles, measurements)
    for role_name, row in leaderboard["roles"].items():
        if role_name == role:
            continue
        if LEADERBOARD_PATH.is_file():
            try:
                previous = _read_json(LEADERBOARD_PATH)
                if role_name in (previous.get("roles") or {}):
                    row.update(previous["roles"][role_name])
            except (OSError, ValueError):
                pass
    written = write_leaderboard(leaderboard, path=Path(args.out),
                                mirror=None if args.no_mirror else INTEL_MIRROR_PATH)
    print(json.dumps({"event": "written", **written,
                      "recommendation": leaderboard["roles"][role]["recommendation"]}, indent=2))
    return 0


def plan(args: argparse.Namespace) -> int:
    roles = load_roles()
    leaderboard = build_leaderboard(roles, {})
    written = write_leaderboard(
        leaderboard, path=Path(args.out),
        mirror=None if args.no_mirror else INTEL_MIRROR_PATH)
    print(json.dumps({"event": "plan", **written,
                      "roles": {name: row["recommendation"]["verdict"]
                                for name, row in leaderboard["roles"].items()}}, indent=2))
    return 0


def restore(args: argparse.Namespace) -> int:
    path = Path(args.out)
    leaderboard = _read_json(path) if path.is_file() else build_leaderboard(load_roles(), {})
    plan_data = restore_plan(args.restore, leaderboard)
    if args.apply:
        import subprocess
        results = []
        for command in plan_data["commands"]:
            proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=300)
            results.append({"command": command, "returncode": proc.returncode,
                            "stdout": (proc.stdout or "").strip()[:400],
                            "stderr": (proc.stderr or "").strip()[:400]})
        plan_data.update({"apply": True, "dry_run": False, "results": results})
    print(json.dumps(plan_data, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="model_scout",
        description="D16 model scout: fixed evals, measured candidates, a written recommendation.")
    parser.add_argument("--run", action="store_true",
                        help="measure models on the GPU (one resident at a time)")
    parser.add_argument("--role", default="bojo-router", help="role to scout (see ty/model_roles.json)")
    parser.add_argument("--models", default="", help="comma-separated candidate tags, already installed")
    parser.add_argument("--no-incumbent", action="store_true",
                        help="do not add the role incumbent to the model list")
    parser.add_argument("--plan", action="store_true", help="write the leaderboard skeleton; no GPU")
    parser.add_argument("--restore", metavar="ROLE", help="print (and with --apply run) the restore plan")
    parser.add_argument("--apply", action="store_true", help="with --restore: run the plan")
    parser.add_argument("--out", default=str(LEADERBOARD_PATH), help="leaderboard path")
    parser.add_argument("--no-mirror", action="store_true", help="do not write state/intel/models.json")
    parser.add_argument("--num-predict", type=int, default=80)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--lock-ttl-s", type=int, default=3600)
    parser.add_argument("--list-evals", action="store_true", help="show eval sets without running anything")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list_evals:
        print(json.dumps({name: {"path": str(eval_path(name).relative_to(ROOT)),
                                 "items": len(load_eval(name)["cases"])}
                          for name in available_evals()}, indent=2))
        return 0
    if args.restore:
        return restore(args)
    if args.run:
        return run(args)
    return plan(args)


if __name__ == "__main__":
    raise SystemExit(main())
