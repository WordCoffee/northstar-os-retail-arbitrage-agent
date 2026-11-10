"""Materialise agents/<name>/ from the registry so a folder can never drift.

Each agent folder holds the five artefacts the blueprint asks for:
  prompt.md  inputs.json  tools.json  schema.json  README.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from specialists import registry  # noqa: E402

PROMPT = """# {label}

You are the **{label}** specialist inside Northstar OS. Bojo routes work to you;
you do the specialist job and return a validated result.

## What you do
{does}

## Required inputs (ask for these; never invent them)
{required}

## Optional inputs
{optional}

## Outputs
{outputs}

## Rules
- Never invent a fact, keyword, ingredient, claim, address, weight, search volume
  or benchmark. If it is missing, ask for it.
- Every number you report must trace to an operator upload, the Brand Kit, the
  local store, or an approved data source.
- Nothing is uploaded to Amazon. You return files the operator uploads themselves.
- Wellness claims: never generate disease or treatment language; flag
  medical-sounding copy for human review.

## Provenance
REBUILT from `specs/{name}.md`. Not adapted from third-party source.
"""


def main() -> int:
    for name, spec in registry.AGENTS.items():
        folder = ROOT / "agents" / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "prompt.md").write_text(PROMPT.format(
            name=name,
            label=spec["label"],
            does=spec["does"],
            required="\n".join(f"- `{i}`" for i in spec["inputs_required"]) or "- none",
            optional="\n".join(f"- `{i}`" for i in spec["inputs_optional"]) or "- none",
            outputs="\n".join(f"- {o}" for o in spec["outputs"]),
        ), encoding="utf-8")
        (folder / "inputs.json").write_text(json.dumps({
            "agent": name,
            "required": spec["inputs_required"],
            "optional": spec["inputs_optional"],
        }, indent=2), encoding="utf-8")
        (folder / "tools.json").write_text(json.dumps({
            "agent": name,
            "allowed_tools": _tools_for(name),
            "needs_gpu": spec.get("needs_gpu", False),
        }, indent=2), encoding="utf-8")
        (folder / "schema.json").write_text(json.dumps({
            "agent": name,
            "outputs": spec["outputs"],
            "validators": spec["validators"],
            "status_values": ["built", "optimized", "planned", "needs_input",
                              "rejected", "unclear", "error"],
        }, indent=2), encoding="utf-8")
        (folder / "README.md").write_text(
            f"# {spec['label']}\n\n{spec['does']}\n\n"
            f"Implementation: `Northstar_backend/specialists/{name}.py`\n"
            f"Spec: `specs/{name}.md`\n"
            f"Chat tool: `{_chat_tool(name)}`\n"
            f"Status: {_status(name)}\n", encoding="utf-8")
    print(f"wrote {len(registry.AGENTS)} agent folders")
    return 0


def _tools_for(name: str) -> list[str]:
    return {
        "package_designer": ["build_package", "create_dieline", "generate_image",
                             "apply_label"],
        "listing_optimizer": ["optimize_listing", "listing_audit", "seo_check",
                              "knowledge_lookup"],
        "ppc_agent": ["ppc_plan", "ads_math", "knowledge_lookup"],
        "image_aplus": ["generate_image", "apply_label", "creative_plan"],
        "social_graphics": ["generate_image", "creative_plan"],
        "video_ugc": ["creative_plan", "generate_image"],
        "content": ["seo_check", "knowledge_lookup"],
        "research": ["corpus_search", "knowledge_lookup", "service_catalog"],
    }.get(name, [])


def _chat_tool(name: str) -> str:
    return {"package_designer": "build_package",
            "listing_optimizer": "optimize_listing",
            "ppc_agent": "ppc_plan"}.get(name, "— (not wired yet)")


def _status(name: str) -> str:
    return {"package_designer": "BUILT + TESTED",
            "listing_optimizer": "BUILT + TESTED",
            "ppc_agent": "BUILT + TESTED",
            "research": "EXISTS (golden_goose_finder) — not routed yet",
            }.get(name, "SPEC ONLY — not built")


if __name__ == "__main__":
    raise SystemExit(main())
