"""Vendored skills: installed packs are rules-blocked, adapted, reviewed.

- Core pack: marketingskills (5) + agency-agents (9).
- Engineering pack: wshobson/agents (24, pinned 46891e7e60da0e52baf1050b7b6391b64e84c6d9).
- VoltAgent pack: awesome-claude-code-subagents (12, pinned 408d3c9eee2d0c75c12a3abb5de29e53c2ca6b9e).

Every skill must carry the Northstar rules block, a service tag, adapted
sections, and pinned provenance. Rejected candidates stay absent, banned
tooling phrases never appear, and token-shaped samples stay sanitized.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILLS = REPO / ".opencode" / "skills"

INSTALLED_CORE = [
    "mk-copywriting",
    "mk-seo-audit",
    "mk-ad-creative",
    "mk-analytics",
    "mk-competitor-profiling",
    "agency-security-ai-code-auditor",
    "agency-test-automation-engineer",
    "agency-api-platform-engineer",
    "agency-ui-designer",
    "agency-fpa-analyst",
    "agency-product-manager",
    "agency-ppc-strategist",
    "agency-search-query-analyst",
    "agency-content-creator",
]

INSTALLED_WSH = [
    "wsh-python-pro",
    "wsh-fastapi-pro",
    "wsh-backend-architect",
    "wsh-backend-security-coder",
    "wsh-database-architect",
    "wsh-test-automator",
    "wsh-tdd-orchestrator",
    "wsh-error-detective",
    "wsh-code-reviewer",
    "wsh-architect-review",
    "wsh-security-auditor",
    "wsh-threat-modeling-expert",
    "wsh-performance-engineer",
    "wsh-api-documenter",
    "wsh-python-structure",
    "wsh-python-patterns",
    "wsh-python-errors",
    "wsh-async-python",
    "wsh-fastapi-templates",
    "wsh-pg-table-design",
    "wsh-openapi-specs",
    "wsh-stride-patterns",
    "wsh-auth-patterns",
    "wsh-sql-optimization",
]

INSTALLED_VOLT = [
    "volt-powershell-7",
    "volt-powershell-51",
    "volt-api-designer",
    "volt-auth-integration-engineer",
    "volt-docker-expert",
    "volt-penetration-tester",
    "volt-powershell-security",
    "volt-ai-writing-auditor",
    "volt-prompt-engineer",
    "volt-database-optimizer",
    "volt-mcp-developer",
    "volt-refactoring-specialist",
]

BANNED_PHRASES = (
    "curl -",
    "wget ",
    "subprocess",
    "os.system",
    "eval(",
    "exec(",
    "credential(",
    "headless=false",
)


def _read(skill: str) -> str:
    return (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")


def test_installed_skills_carry_rules_block_and_provenance():
    for skill in INSTALLED_CORE + INSTALLED_WSH + INSTALLED_VOLT:
        text = _read(skill)
        assert text.startswith("---\n"), skill
        assert "NORTHSTAR RULES" in text, skill
        assert "Service tag & capabilities" in text, skill
        assert re.search(r"commit `[0-9a-f]{40}`", text), skill
    for skill in INSTALLED_CORE:
        assert "Amazon adaptations" in _read(skill), skill
    for skill in INSTALLED_WSH + INSTALLED_VOLT:
        assert "Northstar adaptations" in _read(skill), skill


def test_wshobson_provenance_is_pinned():
    for skill in INSTALLED_WSH:
        text = _read(skill)
        assert "github.com/wshobson/agents" in text, skill
        assert "46891e7e60da0e52baf1050b7b6391b64e84c6d9" in text, skill


def test_volt_provenance_is_pinned():
    for skill in INSTALLED_VOLT:
        text = _read(skill)
        assert "github.com/VoltAgent/awesome-claude-code-subagents" in text, skill
        assert "408d3c9eee2d0c75c12a3abb5de29e53c2ca6b9e" in text, skill


def test_rejected_candidate_is_absent():
    assert not (SKILLS / "agency-multi-platform-publisher").exists()


def test_banned_tooling_phrases_absent():
    for skill in INSTALLED_CORE + INSTALLED_WSH + INSTALLED_VOLT:
        lower = _read(skill).lower()
        for phrase in BANNED_PHRASES:
            assert phrase not in lower, f"{skill}: contains {phrase!r}"


def test_security_auditor_samples_are_sanitized():
    text = _read("agency-security-ai-code-auditor")
    assert not re.search(r"sk-[A-Za-z0-9_-]{16,}", text)
    assert "sk-<EXAMPLE-NOT-A-KEY>" in text


def test_skill_dir_count_matches_manifest():
    dirs = sorted(p.name for p in SKILLS.iterdir() if p.is_dir())
    assert len(dirs) == 2 + len(INSTALLED_CORE) + len(INSTALLED_WSH) + len(INSTALLED_VOLT)
    for skill in ("northstar-data-rules", "northstar-collector"):
        assert skill in dirs
