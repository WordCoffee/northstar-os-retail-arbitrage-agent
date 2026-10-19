"""Input flexibility paths (Thorn v5.0 §Input Flexibility Paths).

Three local front-doors for an incoming request — all deterministic, all offline:

    guided(request)      detects an underspecified request and asks TARGETED
                         questions about the slots it can prove are missing
    discovery(request)   controlled lateral variation: named creative moves with
                         the exact template applied, so a seed run is reproducible
    bulk(request)        reports honestly what the async multi-modal ingest lane
                         can accept TODAY versus what is queued or absent

Honesty contract
----------------
* No model is called. A question here is derived from a pattern that did not
  match in the operator's own text — never invented content.
* `guided` reports the slots it found AND the slots it could not decide on, and
  it never asks more than `max_questions`.
* `discovery` is deterministic for a given seed; the same seed always yields the
  same moves in the same order.
* `bulk` distinguishes IMPLEMENTED lanes from QUEUED ones. It does not advertise
  a capability the repository does not have.
"""
from __future__ import annotations

import random
import re
from typing import Any, Dict, List, Optional, Sequence

MAX_QUESTIONS = 3

# ── task families and the slots each one needs ───────────────────────────────
# Slot = (label, question, patterns that prove it is already answered).
FAMILIES: Dict[str, Dict[str, Any]] = {
    "listing": {
        "match": ("list", "listing", "title", "asin", "seo", "keywords", "bullet"),
        "slots": [
            ("product", "What exact product is this listing for?",
             (r"\b\d+\s?(oz|g|lb|kg|ml|count|ct|pack|pk)\b", r"\bby\b", r"\bbrand\b")),
            ("marketplace", "Which marketplace is the listing going on?",
             (r"\bamazon\b", r"\bet\b", r"\bwalmart\b", r"\bebay\b", r"\bmarketplace\b")),
            ("objective", "Is the goal ranking, conversion, or compliance?",
             (r"\brank", r"\bconver", r"\bcomplian", r"\bindex", r"\bvisibility\b")),
        ],
    },
    "design": {
        "match": ("design", "dieline", "pouch", "label", "carton", "packaging", "mockup", "logo"),
        "slots": [
            ("dimensions", "What are the finished dimensions or fill size?",
             (r"\b\d+\s?(mm|cm|in|inch|oz|g|ml|l)\b", r"\b\d+\s?x\s?\d+")),
            ("substrate", "What material and finish is it printed on?",
             (r"\bkraft\b", r"\bmatte\b", r"\bgloss", r"\buncoat", r"\bpaper\b", r"\bfilm\b",
              r"\bcorrugat", r"\bfoil")),
            ("audience", "Who is the package speaking to?",
             (r"\baudience\b", r"\bcustomer\b", r"\bgift", r"\bpremium\b", r"\bkid", r"\bpet\b")),
        ],
    },
    "sourcing": {
        "match": ("source", "sourcing", "supplier", "buy", "margin", "roi", "profit", "wholesale"),
        "slots": [
            ("market", "Which market or channel are you sourcing for?",
             (r"\bcostco\b", r"\bsam'?s\b", r"\bclub\b", r"\bfaire\b", r"\bsupplier\b",
              r"\bwholesale\b", r"\bmarketplace\b")),
            ("volume", "What volume or pack size are you moving?",
             (r"\b\d+\s?(unit|pack|pk|case|pallet|ct)\b", r"\bper month\b", r"\bqty\b")),
            ("economics", "What margin or ROI floor makes this worth doing?",
             (r"\b\d+\s?%", r"\bmargin\b", r"\broi\b", r"\bprofit\b", r"\bcost\b")),
        ],
    },
    "research": {
        "match": ("research", "compare", "competitor", "market", "trend", "benchmark", "investigate"),
        "slots": [
            ("question", "What is the single question the research must answer?",
             (r"\?", r"\bwhether\b", r"\bis it\b", r"\bshould i\b", r"\bhow many\b")),
            ("scope", "What scope — which brands, products or date range?",
             (r"\bsince\b", r"\bfrom\b", r"\b20\d\d\b", r"\ball\b", r"\bbrand\b", r"\bproduct\b")),
            ("decision", "What decision does this feed?",
             (r"\bdecide\b", r"\bdeciding\b", r"\bchoose\b", r"\blaunch\b", r"\bdrop\b", r"\bkeep\b")),
        ],
    },
}

VAGUE_MARKERS = (
    "make it better", "something", "a few", "stuff", "things", "improve it",
    "fix this", "whatever", "etc", "some kind of", "you know", "more or less",
)

# ── creative discovery: named lateral moves, each with its template ──────────
MOVES: Sequence[Dict[str, str]] = (
    {
        "id": "invert",
        "name": "Invert the binding constraint",
        "apply": "Treat '{subject}' as the thing you may NOT touch, and design around it.",
    },
    {
        "id": "transplant",
        "name": "Cross-domain transplant",
        "apply": "Which mechanic from a completely different field would solve '{subject}'?",
    },
    {
        "id": "scale_up",
        "name": "Extreme scale up",
        "apply": "What would '{subject}' look like at 10x the volume, budget or audience?",
    },
    {
        "id": "scale_down",
        "name": "Extreme scale down",
        "apply": "What is the 10-minute, one-person, zero-budget version of '{subject}'?",
    },
    {
        "id": "remove",
        "name": "Remove the keystone",
        "apply": "Delete the element '{subject}' seems to depend on — what still works?",
    },
    {
        "id": "audience_swap",
        "name": "Audience swap",
        "apply": "How would '{subject}' be built for the opposite customer?",
    },
    {
        "id": "constrain",
        "name": "Add an arbitrary constraint",
        "apply": "Rebuild '{subject}' assuming a hard limit of one page, one word, or one unit.",
    },
    {
        "id": "evidence",
        "name": "Invert the evidence order",
        "apply": "Start from '{subject}' as already true and work backwards to what must exist for it.",
    },
)

# ── bulk ingest: what is actually wired today ───────────────────────────────
BULK_LANES: Sequence[Dict[str, str]] = (
    {"kind": "text", "state": "implemented", "where": "chat + memory bank ingest",
     "note": "Any pasted text can be ingested; no size policy beyond the request body cap."},
    {"kind": "voice", "state": "implemented", "where": "POST /api/chat/voice/transcribe",
     "note": "Local whisper.cpp; audio never leaves the machine."},
    {"kind": "image", "state": "implemented", "where": "design-studio asset store",
     "note": "Stored as assets; no OCR/vision extraction is wired."},
    {"kind": "pdf", "state": "queued", "where": "-",
     "note": "Unstructured PDF extraction is NOT implemented."},
    {"kind": "logs", "state": "queued", "where": "-",
     "note": "Log-dump ingestion is NOT implemented."},
    {"kind": "codebase", "state": "implemented", "where": "purpose_command (AST parse)",
     "note": "Repository mapping runs on demand; nothing is executed."},
)


def _hits(text: str, patterns: Sequence[str]) -> bool:
    low = text.lower()
    return any(re.search(p, low) for p in patterns)


def classify(request: str) -> Dict[str, Any]:
    """Which task family (if any) the request belongs to, with the evidence."""
    text = (request or "").lower()
    scored = []
    for fid, fam in FAMILIES.items():
        hits = [m for m in fam["match"] if m in text]
        if hits:
            scored.append({"family": fid, "score": len(hits), "matched": sorted(hits)})
    scored.sort(key=lambda s: (-s["score"], s["family"]))
    best = scored[0] if scored else None
    vague = [m for m in VAGUE_MARKERS if m in text]
    return {
        "family": best["family"] if best else None,
        "matched": best["matched"] if best else [],
        "candidates": scored[:3],
        "vague_markers": vague,
        "length": len(text.split()),
    }


def guided(request: str, *, max_questions: int = MAX_QUESTIONS) -> Dict[str, Any]:
    """Targeted questions about slots that are provably missing from the request."""
    info = classify(request)
    fam = FAMILIES.get(info["family"] or "")
    if not fam:
        return {
            "family": None,
            "questions": [],
            "answered": [],
            "missing": [],
            "summary": ("No task family matched, so no slot can be proven missing. "
                        "Ask the operator for the goal and the object in one line."),
            "vague_markers": info["vague_markers"],
        }

    answered: List[str] = []
    missing: List[Dict[str, str]] = []
    for slot, question, patterns in fam["slots"]:
        if _hits(request, patterns):
            answered.append(slot)
        else:
            missing.append({"slot": slot, "question": question,
                            "why": "no {0} signal found in the request".format(slot)})

    questions = missing[:max(0, min(max_questions, MAX_QUESTIONS))]
    return {
        "family": info["family"],
        "matched": info["matched"],
        "answered": answered,
        "missing": [m["slot"] for m in missing],
        "questions": questions,
        "vague_markers": info["vague_markers"],
        "summary": (
            f"{len(questions)} question(s) would remove real ambiguity "
            f"({len(answered)} slot(s) already answered)."
            if questions else "Every slot this family needs is already present."
        ),
    }


def _subject(request: str) -> str:
    """A short noun-phrase-ish handle for the request, for move templates."""
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9'-]*", request or "") if len(w) > 3]
    stop = {"that", "this", "with", "from", "your", "have", "need", "want", "make",
            "please", "would", "could", "should", "about"}
    keep = [w for w in words if w.lower() not in stop]
    return " ".join(keep[:4]).lower() or "the request"


def discovery(request: str, *, n: int = 4, seed: int = 0) -> Dict[str, Any]:
    """Controlled lateral variation. Deterministic for a given seed."""
    rng = random.Random(f"{seed}:{request}")
    pool = list(MOVES)
    rng.shuffle(pool)
    chosen = pool[:max(1, min(n, len(pool)))]
    subject = _subject(request)
    return {
        "subject": subject,
        "seed": seed,
        "moves": [{"id": m["id"], "name": m["name"],
                   "prompt": m["apply"].format(subject=subject)} for m in chosen],
        "summary": f"{len(chosen)} lateral move(s) derived from '{subject}' (seed {seed}).",
        "caveat": ("Moves are prompts for a human, not generated answers: nothing "
                   "here invents product facts, prices or claims."),
    }


def bulk() -> Dict[str, Any]:
    """What the async multi-modal ingest lane can accept today."""
    implemented = [b for b in BULK_LANES if b["state"] == "implemented"]
    queued = [b for b in BULK_LANES if b["state"] != "implemented"]
    return {
        "implemented": implemented,
        "queued": queued,
        "summary": (f"{len(implemented)} ingest kind(s) are wired today; "
                    f"{len(queued)} are not (reported, not advertised)."),
        "caveat": "Concurrent unattended ingestion is not implemented; lanes are per-request.",
    }


def paths(request: str, *, seed: int = 0) -> Dict[str, Any]:
    """All three paths for one request, in one report."""
    return {
        "request": request,
        "guided": guided(request),
        "discovery": discovery(request, seed=seed),
        "bulk": bulk(),
    }
