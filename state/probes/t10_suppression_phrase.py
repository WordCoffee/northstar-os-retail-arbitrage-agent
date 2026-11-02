"""PROBE G — the text-suppression phrase must not choose the subject or medium.

Every text-safe render appends SUPPRESSION_PHRASE to the brief. That constant ends
with "botanical illustration only", so a product-pouch brief is rendered as a
herbarium drawing (observed live: a 6 oz pouch request returned a botanical plate).

Required behaviour:
  * the appended phrase forbids lettering, words, typography, logos, barcodes
  * it does NOT name a subject or medium ("botanical illustration" must be gone)
  * the user's own subject words survive in the render prompt
  * an explicit typographic demand in the brief is still suppressed
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Northstar_backend"))

from text_fidelity import sanitize_brief_for_render

failures = []


def check(label, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + label + (f": {detail}" if detail else ""))
    if not ok:
        failures.append(label)


PRODUCT = ("A 6 oz stand-up pouch of organic lion's mane mushroom powder on a warm "
           "neutral background, premium packaging photography")

res = sanitize_brief_for_render(PRODUCT)
prompt = str(res["render_prompt"]).lower()

check("no subject chosen by the suppressor", "botanical" not in prompt,
      prompt[-160:])
# The appended suffix must be purely prohibitive: a positive noun phrase here is a
# scene instruction, and the model renders it instead of the user's brief.
from text_fidelity import SUPPRESSION_PHRASE  # noqa: E402
clauses = [c.strip() for c in str(SUPPRESSION_PHRASE).split(",") if c.strip()]
check("every suppression clause is a prohibition",
      bool(clauses) and all(c.startswith("no ") for c in clauses),
      str(SUPPRESSION_PHRASE)[:120])
check("the phrase is appended verbatim",
      str(res["render_prompt"]).strip().endswith(str(SUPPRESSION_PHRASE).strip()))
for forbidden in ("lettering", "words", "typography", "logo", "barcode"):
    check(f"still suppresses {forbidden}", forbidden in prompt)
check("the subject survives", "pouch" in prompt and "mushroom" in prompt)

typed = sanitize_brief_for_render(PRODUCT + "\nAdd the title text in a serif font, "
                                  "with a logo wordmark")
check("a typographic demand is still stripped",
      "serif font" not in str(typed["render_prompt"]).lower()
      and typed["suppressed_count"] >= 1, str(typed["suppressed_count"]))

if failures:
    print(f"\nRESULT FAIL ({len(failures)}): {failures}")
    raise SystemExit(1)
print("\nRESULT PASS")
raise SystemExit(0)
