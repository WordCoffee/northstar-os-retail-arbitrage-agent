"""CrewAI layer for Ty's Assistant (optional, guarded).

CrewAI lives in `venv-crew` (Python 3.11) because the repo's 3.14 interpreter
cannot build its numpy/pydantic dependency chain. So this module NEVER imports
crewai at module scope and NEVER imports the PIL-dependent modules: it wires the
PURE decision modules (render_bind, aplus_layout, asset_handoff, brand_memory)
into CrewAI tools, and the Flow in `creative_flow.py` stays the orchestrator.

    venv-crew\\Scripts\\python.exe -m Northstar_backend.creative_crew --selftest
    venv-crew\\Scripts\\python.exe -m Northstar_backend.creative_crew --prompt "<brief json>"

Design rules encoded here:
  * the Flow is deterministic; a Crew is used only where judgement is needed
    (authoring the plate prompt, grading an asset);
  * tools call the same functions the rest of the repo calls - no second tool layer;
  * memory is NOT enabled: Northstar's memory_bank is the system of record and it
    gates revisions, so a second vector store would be a competing truth.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

try:  # crewai is optional: the repo must import cleanly without it
    from crewai import Agent, Crew, Process, Task  # type: ignore
    from crewai.tools import BaseTool  # type: ignore
    CREWAI = True
except Exception:  # noqa: BLE001 - absence is a supported state, not an error
    Agent = Crew = Process = Task = object  # type: ignore
    BaseTool = object  # type: ignore
    CREWAI = False


def available() -> bool:
    return CREWAI


# ── tools (pure decision modules only; no PIL, no GPU) ───────────────────────
if CREWAI:
    import aplus_layout
    import asset_handoff
    import brand_memory
    import render_bind

    class MaterialTierTool(BaseTool):
        name: str = "material_tier"
        description: str = (
            "Given product and pricing JSON, return the material tier (premium/standard/value), "
            "margin, blockers and the substrate/finish/lighting clause for the render prompt."
        )

        def _run(self, product_json: str, pricing_json: str = "{}",
                 keywords_json: str = "[]") -> str:
            out = render_bind.bind(json.loads(product_json or "{}"),
                                   pricing=json.loads(pricing_json or "{}"),
                                   keywords=json.loads(keywords_json or "[]"))
            d = out.to_dict()
            d["prompt_suffix"] = render_bind.prompt_suffix(out)
            return json.dumps(d)

    class AplusSpecTool(BaseTool):
        name: str = "aplus_geometry"
        description: str = (
            "Return exact integer A+ module geometry (canvas, copy band, tiles, comparison "
            "cells, responsive scale) for a module kind such as header, three_tiles, comparison."
        )

        def _run(self, kind: str) -> str:
            return json.dumps(aplus_layout.pixel_plan(kind))

    class HandoffTool(BaseTool):
        name: str = "listing_handoff"
        description: str = (
            "Build the Listing Forge payload from a brief JSON and an asset manifest JSON. "
            "Refuses a hero that is not pure-white or not square."
        )

        def _run(self, brief_json: str, assets_json: str = "[]") -> str:
            return json.dumps(asset_handoff.handoff(json.loads(brief_json or "{}"),
                                                    json.loads(assets_json or "[]")))

    class BrandAtomsTool(BaseTool):
        name: str = "brand_atoms"
        description: str = (
            "Extract brand colours, fonts, logo and winning prompts as PROPOSED memory atoms. "
            "Never writes; status is always 'proposed'."
        )

        def _run(self, profile_json: str, account_id: str = "default") -> str:
            brand = brand_memory.extract(json.loads(profile_json or "{}"))
            return json.dumps(brand_memory.propose(brand, account_id=account_id))

    def tools() -> List[Any]:
        return [MaterialTierTool(), AplusSpecTool(), HandoffTool(), BrandAtomsTool()]


def llm():
    """Local OpenAI-compatible endpoint if configured; otherwise CrewAI default.

    Default is `None` so a Crew constructed here never silently calls a paid API.
    """
    if not CREWAI:
        return None
    base = (os.environ.get("CREW_BASE_URL") or "").strip()
    if not base:
        return None
    try:
        from crewai import LLM  # type: ignore
        model = (os.environ.get("CREW_MODEL")
                 or os.environ.get("CREW_MODEL_NAME")
                 or "openai/northstaros-27b-coder")
        return LLM(model=model,
                   base_url=base.rstrip("/"),
                   api_key=(os.environ.get("CREW_API_KEY")
                            or os.environ.get("OPENAI_API_KEY") or "local"))
    except Exception:  # noqa: BLE001
        return None


def build_prompt_crew(render_llm=None) -> Any:
    """Two agents: a Recursive Prompt Architect and a Benchmark Evaluator."""
    if not CREWAI:
        raise RuntimeError("crewai_not_installed (run inside venv-crew)")
    model = render_llm if render_llm is not None else llm()
    architect = Agent(
        role="Recursive Packaging Prompt Architect",
        goal=("Author a single FLUX 3 prompt that yields a PRISTINE, UNPRINTED packaging plate: "
              "correct geometry, material and lighting, and no typography of any kind."),
        backstory=("You have shipped print packaging for a decade and you know that image models "
                   "cannot draw type. You therefore describe material, light and form only, and "
                   "you treat any mention of a brand name as a defect. "
                   "HARD BAN: never write the words emblem, badge, icon, mark, logo, stamp, crest "
                   "or monogram - this model draws lettering when invited. Always say instead: "
                   "'pristine plain surface', 'unprinted uniform texture', 'flat continuous matte "
                   "material'."),
        tools=tools() if CREWAI else [],
        llm=model, verbose=False, allow_delegation=False, max_iter=3,
    )
    evaluator = Agent(
        role="Competitor Benchmark Evaluator",
        goal=("Grade a generated asset against e-commerce listing standards and return a "
              "numeric rubric with named defects - never a vague opinion."),
        backstory=("You have reviewed thousands of Amazon hero images and A+ pages. You score "
                   "composition, product fill, background purity, text legibility and brand "
                   "clarity, and you refuse to score what you cannot see."),
        tools=[], llm=model, verbose=False, allow_delegation=False, max_iter=2,
    )
    return architect, evaluator


def build_crew(render_llm=None) -> Any:
    architect, evaluator = build_prompt_crew(render_llm)
    author = Task(
        description=("Using material_tier for the brief {brief}, write ONE FLUX 3 prompt for a "
                     "blank plate. No brand name, no net weight, no compliance text."),
        expected_output="A single prompt sentence-block under 60 words.",
        agent=architect,
    )
    grade = Task(
        description=("Given the asset metrics {metrics}, return JSON with keys score (0-100), "
                     "defects (list of named issues) and next_action."),
        expected_output="Compact JSON.",
        agent=evaluator,
        context=[author],
    )
    return Crew(agents=[architect, evaluator], tasks=[author, grade],
                process=Process.sequential, memory=False, cache=False, verbose=False)


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--selftest" in args:
        if not available():
            print(json.dumps({"crewai": False, "reason": "not installed in this interpreter"}))
            return 1
        import crewai
        architect, evaluator = build_prompt_crew()
        print(json.dumps({
            "crewai": getattr(crewai, "__version__", "unknown"),
            "agents": [architect.role, evaluator.role],
            "tools": [t.name for t in tools()],
            "llm_configured": llm() is not None,
        }, indent=2))
        return 0
    if "--author" in args:
        brief = args[args.index("--author") + 1] if len(args) > args.index("--author") + 1 else "{}"
        if not available():
            print(json.dumps({"error": "crewai_not_installed"}))
            return 2
        architect, _evaluator = build_prompt_crew()
        task = Task(
            description=("Write ONE FLUX 3 prompt for a pristine, UNPRINTED packaging plate. "
                         "Brief JSON: " + brief + ". No brand name, no net weight, no legal "
                         "copy, no lettering of any kind. Describe only form, material, light "
                         "and background. Under 60 words."),
            expected_output="One prompt sentence-block, under 60 words.",
            agent=architect,
        )
        crew = Crew(agents=[architect], tasks=[task], process=Process.sequential,
                    memory=False, cache=False, verbose=False)
        out = crew.kickoff()
        print(json.dumps({"ok": True, "prompt": str(out).strip()[:800]}, indent=2))
        return 0
    if not available():
        print(json.dumps({"error": "crewai_not_installed"}))
        return 2
    crew = build_crew()
    result = crew.kickoff(inputs={"brief": "{}", "metrics": "{}"})
    print(str(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
