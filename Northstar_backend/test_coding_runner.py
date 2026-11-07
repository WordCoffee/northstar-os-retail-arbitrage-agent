"""The coding runner wires the existing loop + workspace + acceptance with a model."""
from agent_kernel.coding_runner import CodingTask, run_coding_task


def test_loop_writes_required_artifact(tmp_path):
    replies = iter([
        '{"tool":"write","args":{"path":"a.txt","content":"hi"}}',
        '{"tool":"finish","args":{"summary":"done"}}',
    ])
    result = run_coding_task(
        CodingTask(objective="write a.txt", workspace=str(tmp_path),
                   required_files=["a.txt"], max_steps=4),
        model=lambda prompt: next(replies),
    )
    assert result.ok, result.summary
    assert (tmp_path / "a.txt").read_text() == "hi"


def test_acceptance_command_runs_and_can_fail(tmp_path):
    (tmp_path / "check.py").write_text("raise SystemExit(3)\n")
    replies = iter([
        '{"tool":"write","args":{"path":"a.txt","content":"hi"}}',
        '{"tool":"run","args":{"cmd":["python","check.py"]}}',
        '{"tool":"finish","args":{"summary":"done"}}',
        '{"tool":"finish","args":{"summary":"done again"}}',
    ])
    result = run_coding_task(
        CodingTask(objective="write a.txt", workspace=str(tmp_path),
                   required_files=["a.txt"], commands=[["python", "check.py"]],
                   max_steps=6, max_repairs=1),
        model=lambda prompt: next(replies),
    )
    assert not result.ok
    assert "failures" in result.error  # acceptance failure is surfaced, not swallowed


def test_scaffold_writes_missing_configs_only(tmp_path):
    keep = tmp_path / "tsconfig.json"
    keep.write_text('{"compilerOptions":{}}', encoding="utf-8")
    run_coding_task(
        CodingTask(objective="x", workspace=str(tmp_path), scaffold=True,
                   required_files=["a.txt"], max_steps=2),
        model=lambda prompt: '{"tool":"write","args":{"path":"a.txt","content":"hi"}}',
    )
    assert (tmp_path / "package.json").is_file()
    assert keep.read_text(encoding="utf-8") == '{"compilerOptions":{}}'  # never overwritten


def test_builder_mode_prefixes_the_objective(tmp_path):
    seen = {}

    def model(prompt: str) -> str:
        seen["prompt"] = prompt
        return '{"tool":"write","args":{"path":"a.txt","content":"hi"}}'

    run_coding_task(
        CodingTask(objective="build it", workspace=str(tmp_path), builder=True,
                   required_files=["a.txt"], max_steps=2),
        model=model,
    )
    assert "Builder mode" in seen["prompt"]
    assert "write_many" in seen["prompt"]
