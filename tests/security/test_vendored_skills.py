"""Phase 6 vendoring: installed skills are rules-blocked, adapted, reviewed.

The 14 approved skills must carry the Northstar rules block, a service tag,
an Amazon-adaptations section, and a pinned provenance SHA. The rejected
candidate must be absent, banned tooling phrases must not appear, and the
security-auditor's token-shaped samples must be sanitized.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILLS = REPO / ".opencode" / "skills"

INSTALLED = [
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


def test_installed_skills_carry_rules_block_and_provenance():
    for skill in INSTALLED:
        text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
        assert text.startswith("---\n"), skill
        assert "NORTHSTAR RULES" in text, skill
        assert "Amazon adaptations" in text, skill
        assert "Service tag & capabilities" in text, skill
        assert re.search(r"commit `[0-9a-f]{40}`", text), skill


def test_rejected_candidate_is_absent():
    assert not (SKILLS / "agency-multi-platform-publisher").exists()


def test_banned_tooling_phrases_absent():
    for skill in INSTALLED:
        lower = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8").lower()
        for phrase in BANNED_PHRASES:
            assert phrase not in lower, f"{skill}: contains {phrase!r}"


def test_security_auditor_samples_are_sanitized():
    text = (SKILLS / "agency-security-ai-code-auditor" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert not re.search(r"sk-[A-Za-z0-9_-]{16,}", text)
    assert "sk-<EXAMPLE-NOT-A-KEY>" in text


def test_skill_dir_count_matches_manifest():
    # 14 vendored + 2 northstar-authored (data-rules, collector)
    dirs = sorted(p.name for p in SKILLS.iterdir() if p.is_dir())
    assert len(dirs) == 16
    for skill in ("northstar-data-rules", "northstar-collector"):
        assert skill in dirs
