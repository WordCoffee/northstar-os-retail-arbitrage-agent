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
    # Artefact class decides the rubric: listing/hero = strict purity, ad/aplus = hook energy.
    artifact_class: str = "listing"
    # Packaging format decides the geometry profile (box/bottle/tube/pouch).
    geometry: str = "pouch"
    geometry_dims: Dict[str, Any] = field(default_factory=dict)
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
                 prompt_author: Optional[Callable[[Dict[str, Any]], str]] = None,
                 auto_revert: bool = True):
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
        self.auto_revert = bool(auto_revert)

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
        try:
            import geometry_profiles
            _dims = {k: v for k, v in (self.job.geometry_dims or {}).items()
                     if k != "require_print_dpi"}
            geo = geometry_profiles.profile(self.job.geometry, **_dims)
            self.state.steps["bind"]["geometry"] = {
                "kind": geo["kind"], "usable_height_mm": geo.get("usable_height_mm"),
                "quad_px": geo.get("quad"), "dpi_ok": geo["dpi_check"]["ok"],
            }
            # 300 DPI is a PRINT requirement. A render plate is a mockup, so a
            # shortfall is recorded, not enforced - unless the job asks for print.
            if not geo["dpi_check"]["ok"]:
                if (self.job.geometry_dims or {}).get("require_print_dpi"):
                    self.state.blocked.append("resolution_below_300dpi")
                else:
                    self.state.steps["bind"]["geometry"]["dpi_warning"] = "below 300 DPI equivalent"
        except (KeyError, ValueError) as exc:
            self.state.steps["bind"]["geometry"] = {"error": str(exc)[:160]}
            self.state.blocked.append("geometry_invalid")
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
        kind = str(getattr(self.job, "geometry", "pouch") or "pouch").lower()
        surface: Dict[str, Any] = {}
        if kind == "pouch":
            res = self.compose(self.out / "01_plate.png", **self.job.copy)
            surface = {"kind": "pouch", "method": "pouch-measure_face",
                       "quad": res.get("quad"),
                       "geom_residual_px": res.get("geom_residual_px"),
                       "confidence": res.get("confidence"),
                       "measured": res.get("measured")}
        else:
            # Format compositors take a rendered PANEL, not a pouch face. The
            # quad is MEASURED from the plate; a nominal quad is never used as a
            # fallback because that is the defect this step exists to remove.
            import format_compositors
            import geometry_profiles
            import pouch_label
            import surface_measure
            from io import BytesIO
            from PIL import Image
            panel = pouch_label.render_label(**{k: v for k, v in self.job.copy.items()
                                                if k in ("title", "subtitle", "weight", "bullets")})
            plate_bytes = (self.out / "01_plate.png").read_bytes()
            _dims = {k: v for k, v in (self.job.geometry_dims or {}).items()
                     if k != "require_print_dpi"}
            geo = geometry_profiles.profile(kind, **_dims)
            plate = Image.open(BytesIO(plate_bytes)).convert("RGB")
            try:
                measured = surface_measure.measure_surface(
                    plate, kind,
                    wrap_fraction=float(geo.get("wrap_fraction") or 0.92))
            except surface_measure.SurfaceNotMeasurable as exc:
                self.state.blocked.append("surface_unmeasurable")
                self.state.steps["compose"] = {"status": "refused", "kind": kind,
                                               "error": str(exc)[:300]}
                self._save()
                return
            surface = {k: measured.get(k) for k in
                       ("kind", "method", "quad", "geom_residual_px", "confidence",
                        "face", "band", "taper", "crimp_top_px", "crimp_bottom_px",
                        "face_share", "convexity", "width_px", "warnings")}
            kw: Dict[str, Any] = {}
            if kind == "bottle":
                kw["wrap_fraction"] = float(measured.get("wrap_fraction")
                                            or geo.get("wrap_fraction") or 0.92)
            elif kind == "tube":
                # The measured quad already excludes the crimp zones, so the
                # compositor must not inset them a second time. The warp taper
                # is the measured taper, not a constant.
                kw["taper"] = min(0.35, max(0.0, float(measured.get("taper") or 0.0)))
                kw["crimp_top"] = 0
                kw["crimp_bottom"] = 0
            res = format_compositors.composite(kind, plate_bytes, panel,
                                               measured["quad"], **kw)
        self.labelled = res["bytes"]
        (self.out / "02_labelled.png").write_bytes(self.labelled)
        self.state.steps["compose"] = {"residual_px": res.get("geom_residual_px")
                                       if kind == "pouch" else surface.get("geom_residual_px"),
                                       "surface": surface or None,
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
        """Score the hero with the offline rubric unless a scorer was injected.

        The rubric is code, not a model's opinion: contrast, fill, balance, hook
        density, OCR legibility and background purity, each 0-1, composited to
        0-100 with named defects.
        """
        hero = self.out / "03_hero.png"
        if self.score is not None:
            self.state.steps["evaluate"] = self.score(self.state.steps)
        elif hero.exists():
            import asset_rubric
            copy = self.job.copy or {}
            expected = [w.strip(".,") for w in
                        f"{copy.get('title', '')} {copy.get('subtitle', '')}".split()
                        if len(w) > 3][:4]
            cls = str(getattr(self.job, "artifact_class", "listing") or "listing")
            self.state.steps["evaluate"] = asset_rubric.score(
                hero.read_bytes(), cls, expected_copy=expected or None)
            # The plate itself is judged as a MOCKUP: purity is irrelevant there,
            # so its score uses the hook rubric rather than the listing one.
            plate = self.out / "01_plate.png"
            if plate.exists():
                self.state.steps["evaluate"]["plate_mockup"] = asset_rubric.score_hook(
                    plate.read_bytes())
        else:
            self.state.steps["evaluate"] = {"status": "skipped", "reason": "no hero artefact"}
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
        # T1 self-healing: a blocked run restores only the tracked paths it could
        # have touched, then continues. Artefacts are untracked, so a failed
        # render is never deleted by this.
        if self.state.blocked and self.auto_revert and getattr(self, "snapshot_sha", ""):
            try:
                rb = snapshot.rollback_if_red(
                    self.root, self.snapshot_sha, gate_ok=False,
                    paths=["Northstar_backend", "northstar-os-ui", "tools"])
                self.state.steps["rollback"] = {"rolled_back": rb.get("rolled_back"),
                                                "restored": (rb.get("restored") or [])[:12],
                                                "reason": "gate red"}
            except snapshot.SnapshotError as exc:
                self.state.steps["rollback"] = {"error": str(exc)[:200]}
        self.step_report()
        self.state.status = "blocked" if self.state.blocked else "ok"
        self._save()
        return self.state.to_dict()


__all__ = ["CreativeFlow", "CreativeJob", "FlowState", "STEPS"]


