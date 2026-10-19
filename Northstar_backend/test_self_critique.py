"""Self-critique — deterministic checks that quote, and a model layer that fails soft."""
from __future__ import annotations

import self_critique as sc


# ── deterministic layer ──────────────────────────────────────────────────────

def test_unhedged_claim_is_flagged_with_a_quote():
    out = sc.checklist("Write listing copy for a mushroom powder",
                       "This product is certified organic and guaranteed to sell.")
    kinds = {f["kind"] for f in out["findings"]}
    assert "unhedged_claim" in kinds
    flagged = [f for f in out["findings"] if f["kind"] == "unhedged_claim"]
    assert flagged[0]["quote"], "a finding must quote the span it complains about"
    assert out["counts"]["high"] >= 1
    assert out["verdict"] == "issues"


def test_numbers_are_checked_against_the_provided_context():
    clean = sc.checklist("What was the margin?", "The margin was 22%.",
                         context="club margin measured at 22% in March")
    assert "unsourced_number" not in {f["kind"] for f in clean["findings"]}

    dirty = sc.checklist("What was the margin?", "The margin was 37%.")
    bad = [f for f in dirty["findings"] if f["kind"] == "unsourced_number"]
    assert bad and "37" in bad[0]["detail"]
    assert bad[0]["quote"]


def test_topic_drift_detected_when_the_answer_ignores_the_question():
    out = sc.checklist("Should I launch the Lions Mane SKU?",
                       "Barcodes are printed with a thermal transfer printer.")
    assert "possible_topic_drift" in {f["kind"] for f in out["findings"]}


def test_missing_verification_step_on_a_risky_topic():
    out = sc.checklist("Set the price for the powder listing",
                       "Put it at $24.99 and move on.")
    assert "missing_verification_step" in {f["kind"] for f in out["findings"]}

    ok = sc.checklist("Set the price for the powder listing",
                      "Verify the current club cost first, then confirm the margin.")
    assert "missing_verification_step" not in {f["kind"] for f in ok["findings"]}


def test_constraints_are_enforced_concretely():
    out = sc.checklist("Draft it", "one two three four five",
                       constraints={"max_words": 3, "must_include": ["organic"],
                                    "must_not_include": ["cheap"]})
    details = " ".join(f["detail"] for f in out["findings"])
    assert "limit is 3" in details
    assert "missing required phrase 'organic'" in details
    out2 = sc.checklist("Draft it", "a cheap organic thing", constraints={"must_not_include": ["cheap"]})
    assert "forbidden phrase 'cheap'" in " ".join(f["detail"] for f in out2["findings"])


def test_unclosed_markup_is_caught():
    fence = sc.checklist("t", "here:\n```python\nx = 1\n")
    assert "unclosed_code_fence" in {f["kind"] for f in fence["findings"]}
    em = sc.checklist("t", "this is *not closed")
    assert "unclosed_emphasis" in {f["kind"] for f in em["findings"]}


def test_a_good_answer_is_clean():
    out = sc.checklist("Summarise the club finding",
                       "The club cost measured 9.94; verify it before pricing.",
                       context="club cost 9.94")
    assert out["verdict"] == "clean"
    assert out["counts"] == {"high": 0, "medium": 0, "low": 0}


# ── model layer fails soft ───────────────────────────────────────────────────

def test_no_caller_reports_the_model_pass_as_not_run():
    out = sc.critique("t", "answer")
    assert out["model_pass"]["available"] is False
    assert "no model caller" in out["model_pass"]["reason"]
    assert "model pass: not run" in out["summary"]


def test_injected_caller_defects_are_parsed():
    def caller(_prompt):
        return "DEFECT: unsupported claim | FIX: add the source\nDEFECT: vague | FIX: quantify"

    out = sc.critique("t", "answer", caller=caller)
    assert out["model_pass"]["available"] is True
    assert len(out["model_pass"]["defects"]) == 2
    assert "model pass found 2" in out["summary"]


def test_a_failing_caller_is_reported_not_raised():
    def boom(_prompt):
        raise RuntimeError("lane offline")

    out = sc.critique("t", "answer", caller=boom)
    assert out["model_pass"]["available"] is False
    assert "lane offline" in out["model_pass"]["reason"]
    assert out["findings"] is not None            # deterministic layer still ran


def test_refine_lists_fixes_and_does_not_write_the_answer():
    res = sc.critique("t", "This is guaranteed to work.", caller=lambda p: "NO_DEFECTS")
    ref = sc.refine(res)
    assert ref["outline"]
    assert ref["empty"] is False
    assert "not a rewritten answer" in ref["note"]
    assert ref["outline"][0].startswith("[")      # severity-prefixed
