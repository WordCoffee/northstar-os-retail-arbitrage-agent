"""The five spike cases: what the lane is asked, and how it is judged.

Fixed before any candidate runs (see reports/ty/M0.5_spike_plan.md). Each case
carries:

  objective        what the coding lane is told (a contract, not a hint)
  write_paths      the only paths a candidate may change
  read_paths       what it may read (the worktree's own source)
  visible_check    the check the AGENT runs to check itself (copy of the gate,
                   placed inside the worktree at spike_check/, so the loop has a
                   failing signal to repair against)
  acceptance_cmd   the command the AGENT runs to check itself
  gate             the independent check this harness runs afterwards (the same
                   assertions, run from a fresh copy the candidate cannot edit)
  test_file        the targeted test file that must stay green
  module           the file(s) the diff must touch (a scope check, so a pass
                   cannot come from an unrelated edit under a flaky gate)

The gates live in harness/ next to this file. They are copied into the worktree
at `.spike_acceptance/` - OUTSIDE the task's write scope, so a candidate can read
them only if its read scope allows it and can never edit them.
"""
from __future__ import annotations

CASES = {
    "S1": {
        "slug": "s1_cancel_race",
        "problem": ("test_cancel_leased_job_cooperative races: the worker can reach "
                    "SUCCEEDED after a cancel request (illegal transition "
                    "cancel_requested -> succeeded), and a cancel that lands between "
                    "claim and start makes the worker raise "
                    "'job is cancel_requested not leased'"),
        "objective": (
            "BUG: a cooperative cancel is lost when it lands while a leased job is "
            "starting. In Northstar_backend/foundation/jobs_durable.py the worker "
            "(execute_claimed) can raise ValueError('job is cancel_requested not "
            "leased') or drive the job to SUCCEEDED after an operator has already "
            "requested cancellation, because the start transition is only guarded on "
            "LEASED and the success transition does not re-check for a pending cancel.\n"
            "REQUIRED BEHAVIOUR: once a cancel has been requested "
            "(JobState.CANCEL_REQUESTED), a pending cancellation is terminal for the "
            "worker. The worker must acknowledge it (CANCEL_REQUESTED -> CANCELLED via "
            "the existing _finish_cancelled path) and never raise, never retry into a "
            "guarded transition, and never land SUCCEEDED/FAILED/RETRY_WAIT after the "
            "request. An operator cancel that arrives after the worker has already "
            "reached a terminal state must still be refused as not_cancellable - do "
            "not make cancellation unconditionally succeed.\n"
            "CONSTRAINT: do not change the transition table in jobs_state.py to make an "
            "illegal transition legal; the worker must stop instead. Do not edit tests.\n"
            "CHECK: python -m pytest Northstar_backend/foundation/tests/"
            "test_jobs_durable_lifecycle.py -k test_cancel_leased_job_cooperative -x -q"),
        "write_paths": ["Northstar_backend/foundation"],
        "read_paths": ["Northstar_backend/foundation", "Northstar_backend/foundation/tests"],
        "visible": "spike_check/s1_check.py",
        "acceptance_cmds": [
            ["python", "spike_check/s1_check.py"],
            ["python", "-m", "pytest", "Northstar_backend/foundation/tests/"
             "test_jobs_durable_lifecycle.py", "-k",
             "test_cancel_leased_job_cooperative", "-x", "-q"],
        ],
        "read_paths": ["Northstar_backend/foundation", "Northstar_backend/foundation/tests",
                       "spike_check"],
        "gate": ["python", ".spike_acceptance/s1_accept.py"],
        "test_file": "Northstar_backend/foundation/tests/test_jobs_durable_lifecycle.py",
        "module": ["foundation/jobs_durable.py", "foundation/jobs_state.py"],
        "gate_timeout_s": 420,
    },
    "S2": {
        "slug": "s2_product_box",
        "problem": ("picture_scorecard.product_fidelity cannot score a composite whose "
                    "subject detector picks the background (composite with a known "
                    "product_box scores 0.0 instead of a pass)"),
        "objective": (
            "BUG: picture_scorecard.score_case() measures product_fidelity by cropping "
            "both the candidate and the reference with listing_render.subject_bbox(). On "
            "a composited lifestyle plate the candidate's subject detector picks the "
            "linen background, so a correct composite scores 0.0.\n"
            "REQUIRED BEHAVIOUR: score_case must accept an explicit product box. When "
            "case['product_box'] is a sequence of four numbers [x0, y0, x1, y1] in "
            "candidate pixel coordinates, product_fidelity must compare THAT crop of the "
            "candidate against the reference's own product (trim the reference to its "
            "subject/alpha; do not re-run the background detector on the candidate).\n"
            "ACCEPTANCE (hidden test):\n"
            "  composite = renders/autonomy_probe/composite/lifestyle_linen_composite.png\n"
            "  reference = renders/autonomy_probe/composite/lifestyle_linen_cutout.png\n"
            "  row = score_case(image_bytes=composite, case={'id':'e2','surface':\n"
            "        'lifestyle','product_box':[279,308,744,1024]},\n"
            "        reference_bytes=reference, scoring=False)\n"
            "  row['dimensions']['product_fidelity']['score'] >= 85, status 'measured'\n"
            "A measured ceiling with that box is 100.0, so the bar is reachable.\n"
            "CONSTRAINT: existing callers and behaviour must not change - "
            "Northstar_backend/test_picture_scorecard.py must stay green, and with no "
            "product_box the current subject-crop path must keep working.\n"
            "CHECK: python -m pytest Northstar_backend/test_picture_scorecard.py -x -q"),
        "write_paths": ["Northstar_backend/picture_scorecard.py"],
        "read_paths": ["Northstar_backend", "renders/autonomy_probe", "config"],
        "acceptance_cmds": [
            ["python", "spike_check/s2_check.py"],
            ["python", "-m", "pytest",
             "Northstar_backend/test_picture_scorecard.py", "-x", "-q"],
        ],
        "gate": ["python", ".spike_acceptance/s2_accept.py"],
        "test_file": "Northstar_backend/test_picture_scorecard.py",
        "module": ["picture_scorecard.py"],
        "gate_timeout_s": 240,
    },
    "S3": {
        "slug": "s3_documents_contrast",
        "problem": ("the Documents page fails WCAG AA contrast on text it renders: the "
                    "ochre/clay status pills and the unknown pill carry text at ~2.4-3.0:1"),
        "objective": (
            "BUG: /ui/documents renders status pills and low-emphasis text below WCAG AA. "
            "northstar-os-ui/src/styles/app.css (loaded after tokens.css) hardcodes old "
            "colours that were already replaced in tokens.css: .pill-warn color #b8860b "
            "and .pill-unknown color #8a8a7a. tokens.css --ochre (#c4941a) is also used "
            "as pill text. All are below 4.5:1 on the surfaces they sit on.\n"
            "REQUIRED BEHAVIOUR: every text-bearing colour the Documents page uses must "
            "meet WCAG 2.1 AA against its real background (4.5:1 body, 3.0:1 for text "
            ">= 24px). Fix the colour VALUES (tokens and app.css), not the test. Keep the "
            "palette recognisably the same family: a darker ochre/unknown/warn, not black. "
            "Do not remove the pill classes. app.css must not reintroduce a hardcoded "
            "colour that tokens.css already fixed.\n"
            "CHECK: node northstar-os-ui/scripts/check-contrast.mjs"),
        "write_paths": ["northstar-os-ui/src/styles"],
        "read_paths": ["northstar-os-ui/src/styles", "northstar-os-ui/src/pages/customer",
                       "northstar-os-ui/src/components", "northstar-os-ui/scripts",
                       "spike_check"],
        "acceptance_cmds": [
            ["node", "spike_check/s3_check.mjs"],
            ["node", "northstar-os-ui/scripts/check-contrast.mjs"],
        ],
        "gate": ["node", ".spike_acceptance/s3_accept.mjs"],
        "test_file": "northstar-os-ui/scripts/check-contrast.mjs",
        "module": ["styles/tokens.css", "styles/app.css"],
        "gate_timeout_s": 120,
    },
    "S4": {
        "slug": "s4_plate_copy_guard",
        "problem": ("an A+ page renders Shiitake art under a Lion's Mane headline: no "
                    "guard compares the plate's own lettering with the copy it sits under"),
        "objective": (
            "BUG: an A+ module can pair a plate showing 'SHIITAKE' with a Lion's Mane "
            "headline. Nothing compares what the plate says with what the copy says.\n"
            "REQUIRED BEHAVIOUR: add a pure decision function to "
            "Northstar_backend/aplus_render.py:\n"
            "  check_plate_agrees_with_copy(copy: str, plate_ocr: dict | None, *,\n"
            "                               detect=None) -> dict\n"
            "It returns {'ok': bool, 'contradictions': [str], 'copy_terms': [str], "
            "'plate_terms': [str], 'reason': str}.\n"
            "Rules:\n"
            " * A species vocabulary is matched in the COPY and in the PLATE's OCR words "
            "('words' key of plate_ocr): at minimum lions mane / lion's mane, shiitake, "
            "oyster, reishi, chaga, cordyceps, turkey tail, maitake.\n"
            " * If the copy names species A and the plate names species B and not A, "
            "ok is False and 'contradictions' names A and B.\n"
            " * If both name the same species, or the plate names no species, ok is True.\n"
            " * If plate_ocr is None, call detect(plate_png) when a detector is given; if "
            "no detector is given or the OCR failed, ok is False with a reason (an "
            "unreadable plate is not agreement).\n"
            " * Matching is case- and punctuation-insensitive; 'Lion's Mane' and "
            "'lions mane' are the same term.\n"
            "CONSTRAINT: pure function, no network, no image decode unless detect is "
            "passed. Northstar_backend/test_aplus_render.py must stay green.\n"
            "CHECK: python -m pytest Northstar_backend/test_aplus_render.py -x -q"),
        "write_paths": ["Northstar_backend/aplus_render.py"],
        "read_paths": ["Northstar_backend", "spike_check"],
        "acceptance_cmds": [
            ["python", "spike_check/s4_check.py"],
            ["python", "-m", "pytest",
             "Northstar_backend/test_aplus_render.py", "-x", "-q"],
        ],
        "gate": ["python", ".spike_acceptance/s4_accept.py"],
        "test_file": "Northstar_backend/test_aplus_render.py",
        "module": ["aplus_render.py"],
        "gate_timeout_s": 240,
    },
    "S5": {
        "slug": "s5_plate_cleanliness",
        "problem": ("render_text_guard cleans glyphs but leaves faint smudges; there is "
                    "no plate-cleanliness score, so a smeared plate is silently passed"),
        "objective": (
            "BUG: render_text_guard.ensure_text_free() reports cleaned=True as soon as OCR "
            "finds zero boxes, even when the clean pass left faint marks below the OCR "
            "threshold. A smeared plate ships as clean.\n"
            "REQUIRED BEHAVIOUR: add a plate-cleanliness measurement to "
            "Northstar_backend/render_text_guard.py:\n"
            " * module constant RESIDUAL_MARK_THRESHOLD = 0.002 (fraction of the plate's "
            "pixels a residual mark may occupy)\n"
            " * ensure_text_free(..., measure=None) where measure(png) -> dict with key "
            "'residual_mark_fraction' (float 0..1); when measure is None the default "
            "measurement is used (it may return None when no instrument is available, "
            "and then cleanliness is 'unavailable' - never a pass).\n"
            " * the returned dict gains 'plate_clean' (True/False/None) and 'residuals' "
            "(the measure's dict, or a reason).\n"
            " * text-free and plate-clean are DIFFERENT facts: a plate with 0 OCR boxes "
            "but residual_mark_fraction above RESIDUAL_MARK_THRESHOLD has "
            "plate_clean False, keeps cleaned True (text was removed), and its reason "
            "names the residual marks.\n"
            " * below the threshold, plate_clean is True. No detector/measure result "
            "must never be reported as clean.\n"
            "CONSTRAINT: existing keys and behaviour must not change - "
            "Northstar_backend/test_render_text_guard.py must stay green.\n"
            "CHECK: python -m pytest Northstar_backend/test_render_text_guard.py -x -q"),
        "write_paths": ["Northstar_backend/render_text_guard.py"],
        "read_paths": ["Northstar_backend", "spike_check"],
        "acceptance_cmds": [
            ["python", "spike_check/s5_check.py"],
            ["python", "-m", "pytest",
             "Northstar_backend/test_render_text_guard.py", "-x", "-q"],
        ],
        "gate": ["python", ".spike_acceptance/s5_accept.py"],
        "test_file": "Northstar_backend/test_render_text_guard.py",
        "module": ["render_text_guard.py"],
        "gate_timeout_s": 240,
    },
}
