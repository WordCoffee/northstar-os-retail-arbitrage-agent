"""Clean-room UI structural specs: capture once, compare offline, refine against a benchmark.

The capture is supplied (Chrome Connect / Vision / a saved page). This module never browses;
it parses the HTML it is given into a structural spec and compares two specs.

    python -m tools.ty_toolkit.ui_benchmark --spec page.html --reference benchmark.json --out diff.json
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List

LANDMARKS = ("header", "nav", "main", "footer", "aside", "section", "article")
CONTROLS = ("button", "a", "input", "select", "textarea")


class _Spec(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self._heading: List[str] | None = None
        self.headings: List[Dict[str, Any]] = []
        self.landmarks: Counter = Counter()
        self.controls: Counter = Counter()
        self.classes: Counter = Counter()
        self.text: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple[str, str]]) -> None:
        if tag == "title":
            self._in_title = True
        if tag in LANDMARKS:
            self.landmarks[tag] += 1
        if tag in CONTROLS:
            self.controls[tag] += 1
        if tag in ("h1", "h2", "h3"):
            self._heading = []
        for key, value in attrs:
            if key == "class" and value:
                for token in value.split():
                    self.classes[token] += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in ("h1", "h2", "h3") and self._heading is not None:
            self.headings.append({"level": int(tag[1]),
                                  "text": " ".join("".join(self._heading).split())})
            self._heading = None

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._heading is not None:
            self._heading.append(data)
        if data.strip():
            self.text.append(data.strip())


def spec_from_html(html: str, *, url: str = "") -> Dict[str, Any]:
    parser = _Spec()
    parser.feed(html or "")
    text = " ".join(parser.text)
    return {
        "url": url,
        "title": " ".join(parser.title.split()),
        "landmarks": {name: int(parser.landmarks.get(name, 0)) for name in LANDMARKS},
        "headings": parser.headings[:40],
        "controls": {name: int(parser.controls.get(name, 0)) for name in CONTROLS},
        "classes": {name: count for name, count in parser.classes.most_common(30)},
        "text_length": len(text),
        "text_head": text[:240],
    }


def compare(target: Dict[str, Any], reference: Dict[str, Any]) -> Dict[str, Any]:
    """Structural delta with a severity per finding. A missing landmark is not a style nit."""
    findings: List[Dict[str, str]] = []

    def add(severity: str, area: str, detail: str) -> None:
        findings.append({"severity": severity, "area": area, "detail": detail})

    for name in ("header", "nav", "main", "footer"):
        t = int((target.get("landmarks") or {}).get(name, 0))
        r = int((reference.get("landmarks") or {}).get(name, 0))
        if r and not t:
            add("high", "landmarks", f"reference has <{name}>; target has none")
        elif t and not r:
            add("low", "landmarks", f"target adds <{name}> absent from the reference")

    t_titles = [h.get("text", "") for h in target.get("headings") or []]
    r_titles = [h.get("text", "") for h in reference.get("headings") or []]
    if len(r_titles) and len(t_titles) != len(r_titles):
        add("medium", "headings", f"{len(t_titles)} heading(s) vs {len(r_titles)} in the reference")
    if r_titles and t_titles and t_titles[0] != r_titles[0]:
        add("medium", "headings", f"first heading {t_titles[0]!r} vs {r_titles[0]!r}")

    t_controls = target.get("controls") or {}
    r_controls = reference.get("controls") or {}
    for name, expected in r_controls.items():
        got = int(t_controls.get(name, 0))
        if expected and not got:
            add("medium", "controls", f"reference has <{name}> controls; target has none")

    t_classes = set((target.get("classes") or {}))
    r_classes = set((reference.get("classes") or {}))
    if r_classes:
        overlap = len(t_classes & r_classes) / max(1, len(r_classes))
        if overlap < 0.2:
            add("low", "classes", f"class vocabulary overlap {overlap:.0%}; structure may differ")

    if reference.get("title") and target.get("title") != reference.get("title"):
        add("low", "title", f"title {target.get('title')!r} vs {reference.get('title')!r}")

    high = sum(1 for item in findings if item["severity"] == "high")
    medium = sum(1 for item in findings if item["severity"] == "medium")
    score = max(0, 100 - high * 25 - medium * 10 - (len(findings) - high - medium) * 2)
    return {"ok": True, "score": score, "findings": findings,
            "note": "Structural comparison only; it says nothing about visual quality or copy."}


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean-room UI structural benchmark")
    parser.add_argument("--spec", required=True, help="HTML file captured from the target")
    parser.add_argument("--reference", required=True, help="reference spec JSON (or HTML)")
    parser.add_argument("--out", default="")
    ns = parser.parse_args(argv)
    target = spec_from_html(Path(ns.spec).read_text(encoding="utf-8", errors="replace"))
    raw = Path(ns.reference).read_text(encoding="utf-8", errors="replace")
    reference = json.loads(raw) if raw.lstrip().startswith("{") else spec_from_html(raw)
    result = compare(target, reference)
    if ns.out:
        Path(ns.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
