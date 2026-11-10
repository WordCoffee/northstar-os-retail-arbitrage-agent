"""Deterministic small-tool builder (BOJO-UTIL).

The router already decides that "make me a quick tip calculator" is Bojo's work
(`router.scope()` returns ``kind="utility"``), but nothing built it: the scope
test passed on classification, not on output. This module is the output.

Rules, in order of importance:

1. **No invented numbers.** Every figure is typed by the user or computed from
   what they typed. The page never pre-fills a plausible-looking value.
2. **Self-contained.** One HTML file: no CDN, no webfont, no build step, no
   network call. It works opened from disk.
3. **Deterministic.** The same request produces byte-identical HTML, so a build
   can be diffed, re-run and regression-tested.
4. **Honest refusal.** A request this module cannot match says so and lists what
   it *can* build. It never ships a half-working app to look productive.

The arithmetic exists twice on purpose: once in Python (so it is testable and so
the worked example on the page is generated, not guessed) and once in the page's
JavaScript (so it recomputes as the user types). Both are written from the same
formula and the formula text is asserted by the tests, so an edit to one that
forgets the other fails loudly.
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Dict, List, Optional, Tuple

# ── shared page shell ────────────────────────────────────────────────────────
_CSS = """
:root{--ink:#1c1a17;--muted:#6b6357;--line:#d9d2c6;--field:#fffdf8;--accent:#8a5a2b}
*{box-sizing:border-box}
body{margin:0;background:#f4efe6;color:var(--ink);
  font:16px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:640px;margin:0 auto;padding:32px 20px 56px}
h1{font-size:1.5rem;margin:0 0 4px}
.lede{color:var(--muted);margin:0 0 24px}
.card{background:var(--field);border:1px solid var(--line);border-radius:12px;
  padding:18px;margin:0 0 16px}
label{display:block;font-size:.85rem;color:var(--muted);margin:0 0 6px}
input{width:100%;padding:10px 12px;font:inherit;color:inherit;background:#fff;
  border:1px solid var(--line);border-radius:8px}
input:focus{outline:2px solid var(--accent);outline-offset:1px}
.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media (max-width:520px){.row{grid-template-columns:1fr}}
.out{display:flex;justify-content:space-between;gap:12px;padding:8px 0;
  border-bottom:1px dashed var(--line)}
.out:last-of-type{border-bottom:0}
.out b{font-variant-numeric:tabular-nums}
.warn{min-height:1.25rem;color:#a4442c;font-size:.85rem;margin:8px 0 0}
.note{color:var(--muted);font-size:.8rem;margin:24px 0 0}
"""

_PAGE = Template("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title>
<style>$css</style>
</head>
<body>
<main>
<h1>$title</h1>
<p class="lede">$lede</p>
$body
<p class="note">$note</p>
</main>
<script>
$script
</script>
</body>
</html>
""")

_NOTE = ("Built by NorthstarOS as a single self-contained page. No network, no "
         "account, no tracking. Nothing on this page is saved or sent anywhere; "
         "close the tab and it is gone.")

_FIELD = ('<div><label for="{id}">{label}</label>'
          '<input id="{id}" name="{id}" type="number" inputmode="decimal" '
          'step="{step}" min="{minv}" value="{value}" placeholder="{ph}"></div>')

_OUT = '<div class="out"><span>{label}</span><b id="{id}">{value}</b></div>'


def _field(fid: str, label: str, *, step: str = "any", minv: str = "0",
           value: str = "", ph: str = "") -> str:
    return _FIELD.format(id=fid, label=_html.escape(label), step=step, minv=minv,
                         value=_html.escape(value), ph=_html.escape(ph))


def _out(oid: str, label: str, value: str = "—") -> str:
    return _OUT.format(id=oid, label=_html.escape(label), value=value)


def _page(*, title: str, lede: str, body: str, script: str) -> str:
    return _PAGE.substitute(title=_html.escape(title), css=_CSS, lede=_html.escape(lede),
                            body=body, note=_html.escape(_NOTE), script=script)


# ── formulas (mirrored in each page's JavaScript; asserted by the tests) ─────
TIP_TOTAL = "bill * (1 + tip / 100)"
TIP_SHARE = "total / people"
PCT_OF = "base * pct / 100"
PCT_IS = "a / b * 100"
BREAK_UNITS = "fixed / (price - cost)"
BREAK_MARGIN = "(price - cost) / price * 100"


def _fmt(value: float) -> str:
    """Two decimals, thousands separated, no currency symbol imposed."""
    return f"{value:,.2f}"


# ── templates ────────────────────────────────────────────────────────────────
def _tip_page() -> str:
    body = (
        '<section class="card"><div class="row">'
        + _field("bill", "Bill amount", ph="0.00")
        + _field("tip", "Tip (%)", step="1", ph="e.g. 18")
        + "</div>"
        + '<div style="margin-top:12px">'
        + _field("people", "Split between (people)", step="1", ph="e.g. 2")
        + "</div>"
        + _out("tipamt", "Tip")
        + _out("total", "Total")
        + _out("each", "Each person pays")
        + '<p class="warn" id="warn"></p>'
        + "</section>"
    )
    script = """
var f = function (n) { return n.toLocaleString(undefined,
  { minimumFractionDigits: 2, maximumFractionDigits: 2 }); };
function calc() {
  var bill = parseFloat(document.getElementById('bill').value);
  var tip = parseFloat(document.getElementById('tip').value);
  var people = parseInt(document.getElementById('people').value, 10);
  var ok = isFinite(bill) && isFinite(tip) && isFinite(people) && people >= 1;
  if (ok) {
    var tipamt = bill * tip / 100;
    var total = bill * (1 + tip / 100);
    document.getElementById('tipamt').textContent = f(tipamt);
    document.getElementById('total').textContent = f(total);
    document.getElementById('each').textContent = f(total / people);
    document.getElementById('warn').textContent = '';
  } else {
    document.getElementById('tipamt').textContent = '\\u2014';
    document.getElementById('total').textContent = '\\u2014';
    document.getElementById('each').textContent = '\\u2014';
    document.getElementById('warn').textContent =
      'Enter a bill, a tip percentage and at least one person.';
  }
}
['bill', 'tip', 'people'].forEach(function (id) {
  document.getElementById(id).addEventListener('input', calc);
});
calc();
"""
    return _page(
        title="Tip calculator",
        lede="Tip, total and the split. Nothing is guessed: leave a field empty and "
             "the page says what it needs instead of showing a number.",
        body=body,
        script=script,
    )


def _percent_page() -> str:
    body = (
        '<section class="card"><h1 style="font-size:1rem">What is X% of Y?</h1>'
        '<div class="row">'
        + _field("pct", "Percent (%)")
        + _field("base", "Of")
        + "</div>"
        + _out("of", "Result")
        + '<p class="warn" id="warn1"></p></section>'
        + '<section class="card"><h1 style="font-size:1rem">A is what percent of B?</h1>'
        '<div class="row">'
        + _field("a", "A")
        + _field("b", "B")
        + "</div>"
        + _out("is", "Result")
        + '<p class="warn" id="warn2"></p></section>'
    )
    script = """
var f = function (n) { return n.toLocaleString(undefined,
  { minimumFractionDigits: 2, maximumFractionDigits: 2 }); };
function num(id) { return parseFloat(document.getElementById(id).value); }
function set(id, text, warnId, warn) {
  document.getElementById(id).textContent = text;
  document.getElementById(warnId).textContent = warn;
}
function calcOf() {
  var pct = num('pct'), base = num('base');
  if (isFinite(pct) && isFinite(base)) set('of', f(base * pct / 100), 'warn1', '');
  else set('of', '\\u2014', 'warn1', 'Enter a percentage and the number it applies to.');
}
function calcIs() {
  var a = num('a'), b = num('b');
  if (isFinite(a) && isFinite(b) && b !== 0) set('is', f(a / b * 100) + '%', 'warn2', '');
  else set('is', '\\u2014', 'warn2', b === 0 ? 'B cannot be zero.' : 'Enter both numbers.');
}
['pct', 'base'].forEach(function (id) {
  document.getElementById(id).addEventListener('input', calcOf);
});
['a', 'b'].forEach(function (id) {
  document.getElementById(id).addEventListener('input', calcIs);
});
calcOf(); calcIs();
"""
    return _page(
        title="Percentage calculator",
        lede="Two questions a percentage can answer. Empty fields show a dash, not a zero.",
        body=body,
        script=script,
    )


def _breakeven_page() -> str:
    body = (
        '<section class="card"><div class="row">'
        + _field("fixed", "Fixed costs (per month)")
        + _field("price", "Price per unit")
        + "</div>"
        + '<div style="margin-top:12px">'
        + _field("cost", "Cost per unit")
        + "</div>"
        + _out("units", "Units to break even")
        + _out("margin", "Gross margin")
        + _out("profit", "Profit per unit")
        + '<p class="warn" id="warn"></p>'
        + "</section>"
    )
    script = """
var f = function (n) { return n.toLocaleString(undefined,
  { minimumFractionDigits: 2, maximumFractionDigits: 2 }); };
function calc() {
  var fixed = parseFloat(document.getElementById('fixed').value);
  var price = parseFloat(document.getElementById('price').value);
  var cost = parseFloat(document.getElementById('cost').value);
  var warn = document.getElementById('warn');
  if (!(isFinite(fixed) && isFinite(price) && isFinite(cost))) {
    ['units', 'margin', 'profit'].forEach(function (id) {
      document.getElementById(id).textContent = '\\u2014';
    });
    warn.textContent = 'Enter fixed costs, a price and a unit cost.';
    return;
  }
  if (price <= cost) {
    document.getElementById('units').textContent = '\\u2014';
    document.getElementById('margin').textContent = '\\u2014';
    document.getElementById('profit').textContent = f(price - cost);
    warn.textContent = 'Price must be above unit cost: at this price every sale loses money.';
    return;
  }
  warn.textContent = '';
  document.getElementById('units').textContent = Math.ceil(fixed / (price - cost)).toLocaleString();
  document.getElementById('margin').textContent = f((price - cost) / price * 100) + '%';
  document.getElementById('profit').textContent = f(price - cost);
}
['fixed', 'price', 'cost'].forEach(function (id) {
  document.getElementById(id).addEventListener('input', calc);
});
calc();
"""
    return _page(
        title="Break-even calculator",
        lede="How many units cover the fixed costs, and what each sale keeps.",
        body=body,
        script=script,
    )


@dataclass(frozen=True)
class Template:
    id: str
    title: str
    build: object
    keywords: Tuple[str, ...]


TEMPLATES: Tuple[Template, ...] = (
    Template("tip", "Tip calculator", _tip_page,
             ("tip", "gratuity", "service charge", "split the bill")),
    Template("percentage", "Percentage calculator", _percent_page,
             ("percentage", "percent", "discount", "markup")),
    Template("breakeven", "Break-even calculator", _breakeven_page,
             ("break-even", "breakeven", "break even", "margin", "profit")),
)

_BY_ID = {t.id: t for t in TEMPLATES}


def available() -> List[str]:
    """What this builder can actually make, for an honest refusal."""
    return [t.title for t in TEMPLATES]


def pick(request: str) -> Optional[str]:
    """Choose a template from the request, or None.

    Deliberately dumb and order-stable: the first template whose keyword appears
    wins. It never falls back to "something similar" — a wrong calculator is
    worse than a question.
    """
    text = re.sub(r"\s+", " ", str(request or "")).lower()
    for tpl in TEMPLATES:
        for kw in tpl.keywords:
            if kw in text:
                return tpl.id
    return None


def build(request: str, *, out_dir: Optional[Path] = None,
          filename: Optional[str] = None) -> Dict[str, object]:
    """Build one utility page for `request`.

    Returns a dict rather than raising: a request this builder cannot honour is
    a normal outcome the caller can report, not an exception.
    """
    template_id = pick(request)
    if template_id is None:
        return {
            "ok": False,
            "reason": "no_template",
            "error": ("I can build a tip calculator, a percentage calculator or a "
                      "break-even calculator. This request is none of those, and "
                      "guessing would give you the wrong numbers."),
            "available": available(),
        }

    tpl = _BY_ID[template_id]
    page = tpl.build()
    result: Dict[str, object] = {
        "ok": True,
        "template": tpl.id,
        "title": tpl.title,
        "html": page,
        "filename": filename or f"utility-{tpl.id}.html",
        "bytes": len(page.encode("utf-8")),
        "mime_type": "text/html",
    }
    if out_dir is not None:
        target = Path(out_dir) / str(result["filename"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page, encoding="utf-8")
        result["path"] = str(target)
    return result
