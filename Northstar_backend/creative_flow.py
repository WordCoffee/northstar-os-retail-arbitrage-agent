"""Deterministic creative Flow (Ty's Assistant, creative lane).

The orchestrator is a STATE MACHINE, not an LLM: every step is a function with a
named input and a recorded output, resumable from JSON, and every irreversible
action (a render) is preceded by a snapshot and followed by a gate. CrewAI is an
optional layer on top (see creative_crew.py) - it is not required to run a job.

    intake -> bind -> snapshot -> plate -> gate -> compose -> hero -> aplus
           -> evaluate -> memory -> report

Steps that need a model (prompt authoring, geometry choice, scoring) are injected
as callables, so the flow is testable without a GPU and without tokens.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import asset_handoff
import brand_memory
import hardware_guard
import listing_image
import render_bind
import snapshot
import text_fidelity

STEPS = ("intake", "bind", "snapshot", "plate", "gate", "compose", "hero",
         "aplus", "evaluate", "memory", "report")


@dataclass
class CreativeJob:
    job_id: str
    product: Dict[str, Any]
    pricing: Dict[str, Any] = field(default_factory=dict)
    keywords: List[str] = field(default_factory=list)
    buyer: Dict[str, Any] = field(default_factory=dict)
    lifestyle: bool = False
    copy: Dict[str, Any] = field(default_factory=dict)
    aplus_kinds: List[str] = field(default_factory=lambda: ["header", "three_tiles", "comparison"])
    out_dir: str = ""


@dataclass
class FlowState:
    job_id: str
    status: str = "new"
    steps: Dict[str, Any] = field(default_factory=dict)
    blocked: List[str] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CreativeFlow:
    """One job, one state machine. No global state, no hidden retries."""

    def __init__(self, job: CreativeJob, *, root: Path | str = ".",
                 render: Optional[Callable[[str, int, int], bytes]] = None,
                 cutout: Optional[Callable[[bytes], bytes]] = None,
                 compose: Optional[Callable[..., Dict[str, Any]]] = None,
                 score: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
                 prompt_author: Optional[Callable[[Dict[str, Any]], str]] = None):
        self.job = job
        self.root = Path(root).resolve()
        self.out = Path(job.out_dir) if job.out_dir else self.root / "exports" / f"flow_{job.job_id}"
        self.state = FlowState(job_id=job.job_id,
                               started_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        self.render = render
        self.cutout = cutout
        self.compose = compose
        self.score = score
        self.prompt_author = prompt_author

    # â”€â”€ persistence â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _save(self) -> None:
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / "flow_state.json").write_text(
            json.dumps(self.state.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str, **kw) -> "CreativeFlow":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        job = CreativeJob(job_id=data["job_id"], product={"id": data["job_id"]})
        flow = cls(job, **kw)
        flow.state = FlowState(**{k: data[k] for k in
                                  ("job_id", "status", "steps", "blocked",
                                   "started_at", "finished_at") if k in data})
        return flow

    # â”€â”€ steps â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def step_intake(self) -> None:
        if not self.job.product.get("id"):
            self.state.blocked.append("product_id_missing")
        self.state.steps["intake"] = {"ok": not self.state.blocked}
        self._save()

    def step_bind(self) -> None:
        brief = render_bind.bind(self.job.product, pricing=self.job.pricing,
                                 keywords=self.job.keywords, buyer=self.job.buyer,
                                 lifestyle=self.job.lifestyle)
        self.brief = brief
        self.state.steps["bind"] = {"tier": brief.material_tier,
                                    "margin": brief.margin_pct,
                                    "blocked": list(brief.blocked),
                                    "prompt_suffix": render_bind.prompt_suffix(brief)}
        self.state.blocked.extend(brief.blocked)
        self._save()

    def step_snapshot(self) -> None:
        try:
            rec = snapshot.snapshot(self.root, f"flow-{self.job.job_id}")
            self.snapshot_sha = rec["sha"]
            self.state.steps["snapshot"] = {"sha": rec["sha"], "clean": rec["clean_tree"]}
        except snapshot.SnapshotError as exc:
            self.snapshot_sha = ""
            self.state.steps["snapshot"] = {"error": str(exc)[:200]}
        self._save()

    def step_plate(self) -> None:
        hw = hardware_guard.snapshot()
        batch, reason, _ = hardware_guard.plan(1)
        self.state.steps["plate"] = {"vram_ratio": hw.ratio, "temp_c": hw.temp_c,
                                     "allowed": batch, "guard": reason}
        if batch == 0:
            self.state.blocked.append("hardware_guard")
            self._save()
            return
        if self.render is None:
            self.state.steps["plate"]["skipped"] = "no renderer injected"
        else:
            prompt = (self.prompt_author(self.state.steps["bind"])
                      if self.prompt_author else
                      "blank unprinted kraft stand-up pouch, no printing, no text, "
                      "soft studio lighting, 85mm lens")
            png = self.render(prompt, 1024, 1024)
            self.out.mkdir(parents=True, exist_ok=True)
            (self.out / "01_plate.png").write_bytes(png)
            self.plate_bytes = png
            self.state.steps["plate"]["bytes"] = len(png)
        self._save()

    def step_gate(self) -> None:
        if not getattr(self, "plate_bytes", None):
            self.state.steps["gate"] = {"status": "skipped"}
            self._save()
            return
        try:
            res = text_fidelity.assert_plate_clean(self.plate_bytes)
            self.state.steps["gate"] = res
        except text_fidelity.PlateNotClean as exc:
            self.state.blocked.append("dirty_plate")
            self.state.steps["gate"] = {"status": "refused", "error": str(exc)[:300],
                                        "boxes": getattr(exc, "boxes", None)}
        self._save()

    def step_compose(self) -> None:
        if "dirty_plate" in self.state.blocked or self.compose is None:
            self.state.steps["compose"] = {"status": "skipped"}
            self._save()
            return
        res = self.compose(self.out / "01_plate.png", **self.job.copy)
        self.labelled = res["bytes"]
        (self.out / "02_labelled.png").write_bytes(self.labelled)
        self.state.steps["compose"] = {"residual_px": res.get("geom_residual_px"),
                                       "neutralized": (res.get("neutralized") or {}).get("neutralized"),
                                       "bytes": len(self.labelled)}
        self._save()

    def step_hero(self) -> None:
        if not getattr(self, "labelled", None) or self.cutout is None:
            self.state.steps["hero"] = {"status": "skipped"}
            self._save()
            return
        cut = self.cutout(self.labelled)
        hero = listing_image.hero_on_white(cut, size=2000, fill=0.85, shadow=True)
        (self.out / "03_hero.png").write_bytes(hero)
        self.hero_audit = listing_image.audit_white(hero)
        self.state.steps["hero"] = dict(self.hero_audit)
        self._save()

    def step_aplus(self) -> None:
        try:
            import aplus_layout
            specs = {k: aplus_layout.pixel_plan(k) for k in self.job.aplus_kinds}
            (self.out / "aplus_specs.json").write_text(json.dumps(specs, indent=2),
                                                       encoding="utf-8")
            self.state.steps["aplus"] = {"modules": list(specs), "valid": True}
        except (KeyError, ValueError) as exc:
            self.state.steps["aplus"] = {"error": str(exc)[:200]}
        self._save()

    def step_evaluate(self) -> None:
        if self.score is None:
            self.state.steps["evaluate"] = {"status": "skipped"}
            self._save()
            return
        self.state.steps["evaluate"] = self.score(self.state.steps)
        self._save()

    def step_memory(self) -> None:
        brand = brand_memory.extract(self.job.product)  # extract() expects the PROFILE, not the brand sub-dict
        doc = brand_memory.propose(brand, account_id=str(self.job.product.get("account") or "default"))
        self.state.steps["memory"] = {"status": doc["status"], "count": doc["count"],
                                      "persisted": doc["persisted"]}
        self._save()

    def step_report(self) -> None:
        payload = {
            "job_id": self.job.job_id,
            "status": self.state.status,
            "blocked": self.state.blocked,
            "listing": asset_handoff.handoff(getattr(self, "brief", {}), [
                {"url": str(self.out / "03_hero.png"), "width": 2000, "height": 2000,
                 "role": "hero",
                 "pure_white": bool((getattr(self, "hero_audit", {}) or {}).get("corners_pure_white"))},
            ]) if getattr(self, "brief", None) else None,
            "steps": self.state.steps,
        }
        self.state.finished_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        (self.out / "flow_report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.state.steps["report"] = {"path": str(self.out / "flow_report.json")}
        self._save()

    # â”€â”€ driver â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def run(self) -> Dict[str, Any]:
        self.out.mkdir(parents=True, exist_ok=True)
        self.state.status = "running"
        for name in STEPS:
            getattr(self, f"step_{name}")()
            if self.state.blocked and name in ("intake", "bind", "plate", "gate"):
                break
        self.state.status = "blocked" if self.state.blocked else "ok"
        self.step_report()
        self.state.status = "blocked" if self.state.blocked else "ok"
        self._save()
        return self.state.to_dict()


__all__ = ["CreativeFlow", "CreativeJob", "FlowState", "STEPS"]

