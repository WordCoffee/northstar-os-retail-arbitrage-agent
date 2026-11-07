"""One-call entry point for the bounded coding agent.

``run_coding_task`` wires the pieces the kernel already provides — a rooted
workspace, the JSON-tool loop and an acceptance callable — to a model callable.
Tys Assistant and the CLI both go through this, so behaviour cannot drift between
the two entry points.

Two build profiles are supported:

* ``scaffold`` writes package.json/tsconfig.json when they are absent, so the
  model never spends turns inventing build config.
* ``builder`` instructs the first turn to emit every source file in one
  ``write_many`` call, then verify and repair. Measured: a 9-file pipeline went
  green in 2 steps after write_many instead of starving a 24-step budget on
  one-file-per-turn writes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from .coding_agent import Acceptance, CodingAgent, CodingResult, Model
from .coding_tools import Workspace
from .local_model import make_local_model
from .tys_adapter import make_workspace_acceptance

BUILDER_PREFIX = (
    "Builder mode. Your FIRST turn must be a single write_many call containing "
    "every source file; do not read files first. After writing, run the acceptance "
    "command and repair with write_many until it passes, then finish.\n\n"
)

TS_SCAFFOLD: Dict[str, Any] = {
    "package.json": {
        "name": "agent-ws", "private": True, "version": "1.0.0",
        "devDependencies": {"typescript": "^5.7.2", "@types/node": "^22.10.2"},
    },
    "tsconfig.json": {
        "compilerOptions": {
            "target": "ES2022", "module": "commonjs", "strict": True,
            "esModuleInterop": True, "skipLibCheck": True, "noEmit": True,
            "types": ["node"],
        },
        "include": ["src/**/*.ts"],
    },
}


def ensure_ts_scaffold(workspace: str | Path) -> List[str]:
    """Create package.json/tsconfig.json when missing; never overwrite."""
    root = Path(workspace)
    root.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    for name, payload in TS_SCAFFOLD.items():
        path = root / name
        if not path.exists():
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            written.append(name)
    return written


@dataclass
class CodingTask:
    objective: str
    workspace: str
    commands: Sequence[Sequence[str]] = ()
    required_files: Sequence[str] = ()
    max_steps: int = 12
    max_repairs: int = 1
    required_artifact: str = ""
    builder: bool = False
    scaffold: bool = False


def _acceptance(workspace: str, task: CodingTask) -> Optional[Acceptance]:
    if not task.commands and not task.required_files:
        return None
    return make_workspace_acceptance(
        workspace,
        {"commands": [list(c) for c in task.commands],
         "required_files": list(task.required_files)},
    )


def run_coding_task(
    task: CodingTask,
    *,
    model: Optional[Model] = None,
    acceptance: Optional[Acceptance] = None,
    workspace: Optional[Workspace] = None,
) -> CodingResult:
    """Run the observe -> act -> verify -> repair loop against one objective."""
    if task.scaffold:
        ensure_ts_scaffold(task.workspace)
    objective = (BUILDER_PREFIX if task.builder else "") + task.objective
    ws = workspace or Workspace(task.workspace)
    check = acceptance or _acceptance(str(ws.root), task)
    agent = CodingAgent(
        ws,
        model or make_local_model(),
        max_steps=max(1, int(task.max_steps)),
        max_repairs=max(0, int(task.max_repairs)),
        acceptance=check,
        required_artifact=task.required_artifact,
    )
    return agent.run(objective)


def result_dict(result: CodingResult) -> Dict[str, Any]:
    data = result.to_dict()
    data.setdefault("acceptance_recovered", result.acceptance_recovered)
    return data
