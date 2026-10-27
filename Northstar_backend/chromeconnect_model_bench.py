"""Chrome Connect model benchmark (Phase 4).

Benchmarks local Ollama models as the browser brain for the AI loop.
Scores: pass rate, steps, tokens, wall time per task.

Usage:
    python chromeconnect_model_bench.py [--models m1,m2] [--tasks n] [--output report.md]

Provenance: In-house benchmark. No external code. Uses Ollama API (local, free).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chromeconnect_ai_loop as ail
import chromeconnect_observation as obs

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")

# Candidate models (available on this machine)
CANDIDATE_MODELS = [
    "northstaros-qwen3.8:27b",
    "qwen3.8-27b-coder:latest",
    "northstaros-qwen3.8:27b-ctx64k-orig",
]

# Fixture tasks: (goal, html_fixture_name)
BENCH_TASKS = [
    ("extract title and price from this page", "costco_product_page"),
    ("extract product names and prices from search results", "costco_search_results"),
    ("extract ASIN, title, price, and BSR from the table", "sellersprite_dashboard"),
    ("extract buy box price, fees, net profit, and ROI", "selleramp_analysis"),
    ("find and click the search button", "sellersprite_dashboard"),
    ("extract all product titles and prices", "product_listing"),
    ("scroll down and read more content", "large_table"),
    ("extract the page title and main heading", "agentconnect_home"),
    ("find the login form fields", "login_page_generic"),
    ("extract all links from the navigation", "navigation_page"),
]


def _ollama_chat(model: str, prompt: str, timeout_s: float = 60.0) -> Optional[str]:
    """Call Ollama chat API. Returns response text or None."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.1, "num_ctx": 4096},
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat", data=data, method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("message", {}).get("content", "")
    except Exception as e:
        return None


def _build_decision_prompt(goal: str, snapshot: Dict) -> str:
    """Build a prompt for the model to decide the next action."""
    elements = snapshot.get("elements", [])
    # Compact element summary
    el_summary = []
    for el in elements[:30]:
        text = el.get("text", "")[:60]
        el_summary.append(f"  {el['ref']}: <{el.get('tag','')}> {text}")
    el_text = "\n".join(el_summary) if el_summary else "  (no interactive elements)"

    return f"""You are a browser automation agent. Given a goal and a page snapshot, decide the next action.

GOAL: {goal}

PAGE SNAPSHOT (interactive elements):
{el_text}

Available tools: navigate(url), snapshot(), click(ref), type(ref, text), scroll(direction), extract(schema), wait(condition), finish(result), give_up(reason)

Respond with ONLY a JSON object: {{"tool": "...", "args": {{...}}}}
No explanation. No markdown. Just JSON."""


def _parse_action(response: str) -> Optional[Dict[str, Any]]:
    """Parse model response into an action dict."""
    if not response:
        return None
    # Try to extract JSON
    text = response.strip()
    # Remove markdown code blocks
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                text = part
                break
    try:
        action = json.loads(text)
        if "tool" in action:
            return action
    except json.JSONDecodeError:
        # Try to find JSON in text
        import re
        match = re.search(r'\{[^}]+\}', text)
        if match:
            try:
                action = json.loads(match.group(0))
                if "tool" in action:
                    return action
            except json.JSONDecodeError:
                pass
    return None


def _make_decision_fn(model: str) -> Callable:
    """Create a decision function that uses the given Ollama model."""
    def decision_fn(goal: str, snapshot: Dict) -> Optional[Dict[str, Any]]:
        prompt = _build_decision_prompt(goal, snapshot)
        response = _ollama_chat(model, prompt)
        return _parse_action(response)
    return decision_fn


def benchmark_model(model: str, tasks: List[Tuple[str, str]], fixture_dir: str) -> Dict[str, Any]:
    """Benchmark a single model on all tasks."""
    import chromeconnect_observation as obs

    decision_fn = _make_decision_fn(model)
    results = []
    total_steps = 0
    total_tokens = 0
    total_time = 0.0
    successes = 0

    for goal, fixture_name in tasks:
        html_text = obs.load_fixture(fixture_name)
        if html_text is None:
            results.append({"task": goal, "fixture": fixture_name, "error": "fixture not found"})
            continue

        def html_provider(url):
            return html_text

        start = time.monotonic()
        result = ail.run_loop(goal, html_provider, decision_fn=decision_fn)
        elapsed = time.monotonic() - start

        success = result.get("success", False)
        if success:
            successes += 1
        total_steps += result.get("steps", 0)
        total_tokens += result.get("tokens", 0)
        total_time += elapsed

        results.append({
            "task": goal,
            "fixture": fixture_name,
            "success": success,
            "steps": result.get("steps", 0),
            "tokens": result.get("tokens", 0),
            "time_s": round(elapsed, 3),
            "gave_up_reason": result.get("gave_up_reason"),
        })

    n = len(tasks)
    return {
        "model": model,
        "tasks": n,
        "successes": successes,
        "pass_rate": round(successes / n, 4) if n else 0,
        "avg_steps": round(total_steps / n, 2) if n else 0,
        "avg_tokens": round(total_tokens / n, 1) if n else 0,
        "avg_time_s": round(total_time / n, 3) if n else 0,
        "total_time_s": round(total_time, 3),
        "details": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Chrome Connect model benchmark")
    parser.add_argument("--models", default=None, help="Comma-separated model names")
    parser.add_argument("--tasks", type=int, default=len(BENCH_TASKS), help="Number of tasks")
    parser.add_argument("--output", default=None, help="Output markdown file")
    args = parser.parse_args()

    models = args.models.split(",") if args.models else CANDIDATE_MODELS
    tasks = BENCH_TASKS[:args.tasks]

    print(f"Benchmarking {len(models)} models on {len(tasks)} tasks...")
    print(f"Ollama URL: {OLLAMA_URL}")
    print()

    all_results = []
    for model in models:
        print(f"  Testing {model}...")
        r = benchmark_model(model, tasks, None)
        all_results.append(r)
        print(f"    pass_rate={r['pass_rate']}, avg_steps={r['avg_steps']}, "
              f"avg_tokens={r['avg_tokens']}, avg_time={r['avg_time_s']}s")
        print()

    # Generate report
    report_lines = [
        "# Chrome Connect Model Benchmark Report",
        "",
        f"Date: {__import__('datetime').datetime.now().isoformat()}",
        f"Tasks: {len(tasks)}",
        f"Models tested: {len(models)}",
        "",
        "## Summary",
        "",
        "| Model | Pass Rate | Avg Steps | Avg Tokens | Avg Time (s) | Total Time (s) |",
        "|-------|-----------|-----------|------------|--------------|----------------|",
    ]
    for r in all_results:
        report_lines.append(
            f"| {r['model']} | {r['pass_rate']} | {r['avg_steps']} | "
            f"{r['avg_tokens']} | {r['avg_time_s']} | {r['total_time_s']} |"
        )
    report_lines.append("")

    # Per-task breakdown
    for r in all_results:
        report_lines.append(f"## {r['model']}")
        report_lines.append("")
        report_lines.append("| Task | Fixture | Success | Steps | Tokens | Time (s) | Gave Up Reason |")
        report_lines.append("|------|---------|---------|-------|--------|----------|----------------|")
        for d in r["details"]:
            report_lines.append(
                f"| {d['task'][:40]} | {d['fixture']} | {d.get('success', 'ERR')} | "
                f"{d.get('steps', '-')} | {d.get('tokens', '-')} | "
                f"{d.get('time_s', '-')} | {d.get('gave_up_reason', '-')} |"
            )
        report_lines.append("")

    # Recommendation
    if all_results:
        best = max(all_results, key=lambda r: (r["pass_rate"], -r["avg_time_s"]))
        report_lines.append("## Recommendation")
        report_lines.append("")
        report_lines.append(f"**Best model:** {best['model']} (pass_rate={best['pass_rate']}, "
                          f"avg_time={best['avg_time_s']}s)")
        report_lines.append("")
        report_lines.append("Note: Only 27B models are available on this machine. "
                          "9B and 12B candidates from the plan are not installed.")

    report = "\n".join(report_lines)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(report)
        print(f"Report written to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
