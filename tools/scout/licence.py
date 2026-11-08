"""Licence engine (D11 / A19).

One question, answered from evidence: *may this finding be adopted by a
commercial product*.  The answer is never inferred from a badge or a README
sentence.  It is derived from the licence string the source actually returned
(GitHub ``spdx_id``, Hugging Face ``license:`` tag, PyPI ``info.license`` /
classifiers, npm ``license`` field).

Vocabulary is closed on purpose.  ``normalise()`` returns a canonical SPDX-ish
id or ``"unknown"``; ``classify()`` returns one of :data:`CLASSES`.  An
unrecognised string is ``unknown``, never permissive: an unparsed licence is a
licence we have not read.
"""
from __future__ import annotations

import re
from typing import Iterable, List

CLASSES = ("permissive", "public-domain", "weak-copyleft", "copyleft",
           "noncommercial", "proprietary", "unknown")

#: Canonical ids we recognise, with their class.  Keys are uppercase.
_KNOWN = {
    "MIT": "permissive",
    "MIT-0": "permissive",
    "APACHE-2.0": "permissive",
    "APACHE-1.1": "permissive",
    "BSD-2-CLAUSE": "permissive",
    "BSD-3-CLAUSE": "permissive",
    "BSD-4-CLAUSE": "permissive",
    "ISC": "permissive",
    "0BSD": "permissive",
    "ZLIB": "permissive",
    "BSL-1.0": "permissive",
    "PSF-2.0": "permissive",
    "POSTGRESQL": "permissive",
    "X11": "permissive",
    "WTFPL": "public-domain",
    "UNLICENSE": "public-domain",
    "CC0-1.0": "public-domain",
    "CC-BY-4.0": "permissive",
    "CC-BY-SA-4.0": "weak-copyleft",
    "MPL-2.0": "weak-copyleft",
    "LGPL-2.1": "weak-copyleft",
    "LGPL-3.0": "weak-copyleft",
    "EPL-2.0": "weak-copyleft",
    "GPL-2.0": "copyleft",
    "GPL-3.0": "copyleft",
    "AGPL-3.0": "copyleft",
    "CC-BY-NC-4.0": "noncommercial",
    "CC-BY-NC-SA-4.0": "noncommercial",
    "CC-BY-NC-ND-4.0": "noncommercial",
    "PROPRIETARY": "proprietary",
    "COMMERCIAL": "proprietary",
    "UNKNOWN": "unknown",
}

_ALIASES = {
    "": "unknown", "NONE": "unknown", "NOASSERTION": "unknown",
    "UNSTATED": "unknown", "OTHER": "unknown", "UNSPECIFIED": "unknown",
    "SEE LICENSE IN README": "unknown", "SEE LICENSE IN LICENSE": "unknown",
    "APACHE 2.0": "Apache-2.0", "APACHE2": "Apache-2.0",
    "APACHE-2": "Apache-2.0", "APACHE LICENSE 2.0": "Apache-2.0",
    "BSD": "BSD-3-Clause", "BSD 3-CLAUSE": "BSD-3-Clause",
    "BSD 2-CLAUSE": "BSD-2-Clause", "BSD-3": "BSD-3-Clause",
    "GPL": "GPL-3.0", "GPLV3": "GPL-3.0", "GPL-3": "GPL-3.0",
    "GPLV2": "GPL-2.0", "GPL-2": "GPL-2.0",
    "AGPL": "AGPL-3.0", "AGPLV3": "AGPL-3.0", "AGPL-3": "AGPL-3.0",
    "LGPL": "LGPL-3.0", "LGPLV3": "LGPL-3.0", "LGPL-3": "LGPL-3.0",
    "MPL": "MPL-2.0", "MPL2": "MPL-2.0",
    "PUBLIC DOMAIN": "Unlicense", "PUBLIC-DOMAIN": "Unlicense",
    "CC0": "CC0-1.0", "CC-0": "CC0-1.0",
    "UNLICENCE": "Unlicense",
    "PROP": "proprietary",
    "NON-COMMERCIAL": "noncommercial", "NONCOMMERCIAL": "noncommercial",
    "NON COMMERCIAL": "noncommercial", "RESEARCH ONLY": "noncommercial",
    "CC-BY-NC": "CC-BY-NC-4.0", "CC BY-NC 4.0": "CC-BY-NC-4.0",
    "CC-BY-NC-SA": "CC-BY-NC-SA-4.0", "CC-BY-NC-ND": "CC-BY-NC-ND-4.0",
    "CC-BY": "CC-BY-4.0", "CC-BY-SA": "CC-BY-SA-4.0",
}

#: Display casing for canonical ids (the lookup table is uppercase-only).
_DISPLAY = {
    "MIT": "MIT", "MIT-0": "MIT-0", "ISC": "ISC", "APACHE-2.0": "Apache-2.0",
    "APACHE-1.1": "Apache-1.1", "BSD-2-CLAUSE": "BSD-2-Clause",
    "BSD-3-CLAUSE": "BSD-3-Clause", "BSD-4-CLAUSE": "BSD-4-Clause",
    "ZLIB": "Zlib", "PSF-2.0": "PSF-2.0", "POSTGRESQL": "PostgreSQL",
    "X11": "X11", "WTFPL": "WTFPL", "UNLICENSE": "Unlicense",
    "MPL-2.0": "MPL-2.0", "LGPL-2.1": "LGPL-2.1", "LGPL-3.0": "LGPL-3.0",
    "GPL-2.0": "GPL-2.0", "GPL-3.0": "GPL-3.0", "AGPL-3.0": "AGPL-3.0",
    "EPL-2.0": "EPL-2.0", "BSL-1.0": "BSL-1.0", "CC0-1.0": "CC0-1.0",
    "CC-BY-4.0": "CC-BY-4.0", "CC-BY-SA-4.0": "CC-BY-SA-4.0",
    "CC-BY-NC-4.0": "CC-BY-NC-4.0", "CC-BY-NC-SA-4.0": "CC-BY-NC-SA-4.0",
    "CC-BY-NC-ND-4.0": "CC-BY-NC-ND-4.0", "PROPRIETARY": "proprietary",
    "COMMERCIAL": "commercial", "UNKNOWN": "unknown",
    "NONCOMMERCIAL": "noncommercial",
}

_NC_RE = re.compile(r"(?:^|[-_\s])NC(?:[-_\s]|$)|NON[-_ ]?COMMERCIAL|"
                    r"RESEARCH[-_ ]ONLY|NONCOMMERCIAL", re.I)
_PROPRIETARY_RE = re.compile(r"PROPRIETARY|ALL RIGHTS RESERVED", re.I)

#: Full licence texts (PyPI ``info.license`` is often the whole file).  Checked
#: before the id scan because a GPL text *contains* the words of other licences.
_TEXT_HINTS = (
    (r"GNU AFFERO GENERAL PUBLIC", "AGPL-3.0"),
    (r"GNU LESSER GENERAL PUBLIC", "LGPL-3.0"),
    (r"GNU GENERAL PUBLIC LICENSE", "GPL-3.0"),
    (r"MOZILLA PUBLIC LICENSE", "MPL-2.0"),
    (r"ECLIPSE PUBLIC LICENSE", "EPL-2.0"),
    (r"APACHE LICENSE|APACHE SOFTWARE LICENSE", "Apache-2.0"),
    (r"PERMISSION IS HEREBY GRANTED|MIT LICENSE", "MIT"),
    (r"REDISTRIBUTION AND USE IN SOURCE AND BINARY FORMS", "BSD-3-Clause"),
    (r"UNLICENSE|PUBLIC DOMAIN", "Unlicense"),
)

#: PyPI trove classifiers, used only when ``info.license`` is empty.
_CLASSIFIER_MAP = (
    ("MIT License", "MIT"),
    ("Apache Software License", "Apache-2.0"),
    ("BSD License", "BSD-3-Clause"),
    ("ISC License", "ISC"),
    ("Mozilla Public License 2.0", "MPL-2.0"),
    ("GNU Affero General Public License v3", "AGPL-3.0"),
    ("GNU Lesser General Public License v3", "LGPL-3.0"),
    ("GNU Lesser General Public License v2", "LGPL-2.1"),
    ("GNU General Public License v3", "GPL-3.0"),
    ("GNU General Public License v2", "GPL-2.0"),
    ("The Unlicense", "Unlicense"),
    ("Creative Commons Zero", "CC0-1.0"),
)


def _strip_version_suffix(value: str) -> str:
    return re.sub(r"-(?:ONLY|OR-LATER)$", "", value)


def normalise(value: object) -> str:
    """Canonical licence id, or ``"unknown"``.  Never guesses."""
    if value is None:
        return "unknown"
    raw = str(value).strip().strip("()[]\"'")
    if not raw:
        return "unknown"
    key = re.sub(r"\s+", " ", raw).upper()
    if key in _ALIASES:
        return _ALIASES[key]
    key = _strip_version_suffix(key.replace("_", "-"))
    if key in _KNOWN:
        return _DISPLAY.get(key, key)
    if _NC_RE.search(raw):
        return "noncommercial"
    if _PROPRIETARY_RE.search(raw):
        return "proprietary"
    for pattern, canonical in _TEXT_HINTS:
        if re.search(pattern, raw, re.I):
            return canonical
    # A string that merely contains a known id ("MIT License") is that licence.
    for canonical in sorted(_KNOWN, key=len, reverse=True):
        if canonical in key:
            return _DISPLAY.get(canonical, canonical)
    return "unknown"


def classify(canonical: str) -> str:
    cls = _KNOWN.get((canonical or "").upper())
    if cls:
        return cls
    if (canonical or "").lower() == "unknown":
        return "unknown"
    return "unknown"


def commercial_ok(cls: str) -> bool:
    """Commercial use permitted *by the licence* — not a lane decision."""
    return cls in ("permissive", "public-domain", "weak-copyleft", "copyleft")


def cleanliness(cls: str) -> float:
    """0..1 weight used by ranking.  Unknown is low, non-commercial is zero."""
    return {
        "permissive": 1.0,
        "public-domain": 1.0,
        "weak-copyleft": 0.7,
        "copyleft": 0.45,
        "unknown": 0.2,
        "noncommercial": 0.0,
        "proprietary": 0.0,
    }.get(cls, 0.0)


def from_classifiers(classifiers: Iterable[str]) -> str:
    """Best-effort licence from PyPI trove classifiers (evidence, not a badge)."""
    for classifier in classifiers or ():
        text = str(classifier)
        if "License ::" not in text:
            continue
        for needle, canonical in _CLASSIFIER_MAP:
            if needle.lower() in text.lower():
                return canonical
    return "unknown"


def describe(canonical: str) -> str:
    """One line for the report: canonical id, class, adoptability."""
    cls = classify(canonical)
    return f"{canonical} ({cls}, commercial={'yes' if commercial_ok(cls) else 'no'})"


def is_adoptable_licence(canonical: str) -> bool:
    """Only clean, commercially usable licences may ever reach ``adopt``.

    Copyleft is technically commercial but is held for review because the
    provider suite refuses unreviewed AGPL/GPL for the cloud lane.
    """
    return classify(canonical) in ("permissive", "public-domain", "weak-copyleft")


def all_classes() -> List[str]:
    return list(CLASSES)
