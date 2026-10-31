"""Dynamic FLUX 3 prompt author over the local 27B lane.

The live runner must not fall back to a fixed template: the prompt is authored
per format from the job, the geometry profile, brand facts from the Memory Bank
and explicit lighting/camera/background constraints. The local lane speaks the
OpenAI-compatible API on 127.0.0.1:8080 (llama.cpp / llama-server).

Fail-closed contract:

    lane down / timeout / empty completion -> PromptAuthorUnavailable
    caller -> block the run; never render on a template it did not author

No paid provider, no cloud call. The endpoint is local by default; an operator
may point NORTHSTAR_AUTHOR_URL at another local port, but a remote host is not
the intended configuration and is reported in the result.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

import geometry_profiles

DEFAULT_URL = "http://127.0.0.1:8080/v1"
DEFAULT_MODEL = "northstaros-27b-coder"
DEFAULT_LIGHTING = "soft diffused studio key light from upper-left, gentle fill, no hard specular"
DEFAULT_CAMERA = "85mm product lens, eye-level three-quarter view, subject fully in frame"
DEFAULT_BACKGROUND = "seamless neutral light-grey studio background, no visible floor, no horizon"

#: A verbal form note per format. The geometry dict carries millimetres; the
#: model also needs the SHAPE, or a "tube" can come back as an open cylinder.
FORM_NOTES = {
    "pouch": "stand-up pouch with a sealed top weld/zipper header and a bottom gusset",
    "box": "straight tuck box with a front panel, side panels and folded tuck flaps",
    "bottle": "cylindrical bottle with a shoulder, a narrow neck and a screw cap",
    "tube": "cosmetic tube with a flat heat-sealed crimp at one end and a cap at the other",
}

SYSTEM = (
    "You are the Recursive Packaging Prompt Architect for Northstar OS. "
    "Write ONE FLUX 3 prompt for a PRISTINE, UNPRINTED packaging plate. "
    "Describe only form, material, light, camera and background. "
    "HARD BANS: no brand name, no product name, no net weight, no legal copy, "
    "no lettering, no logo, no emblem, no badge, no icon, no stamp, no crest, "
    "no monogram, no label artwork. Say 'pristine plain surface', 'unprinted "
    "uniform texture' or 'flat continuous matte material' instead. "
    "The output must be a single prompt block under 70 words. "
    "Do not add commentary, quotes, markdown or a preamble."
)

#: Words that would invite the image model to paint type onto the plate.
_BANNED = re.compile(
    r"\b(logo|logotype|emblem|badge|icon|stamp|crest|monogram|label|typography|"
    r"lettering|text|wordmark)\b", re.IGNORECASE)


class PromptAuthorUnavailable(RuntimeError):
    """The local author lane did not produce a usable prompt."""


def _brand_facts(job: Any) -> Dict[str, Any]:
    product = dict(getattr(job, "product", {}) or {})
    account = str(product.get("account") or "default")
    facts: Dict[str, Any] = {}
    try:
        import brand_memory
        brand = brand_memory.extract(product)
        facts = {"colors": brand.get("colors") or [],
                 "fonts": brand.get("fonts") or {},
                 "logo": bool(brand.get("logo"))}
    except Exception:  # noqa: BLE001 - brand memory is context, not a requirement
        facts = {}
    context = ""
    try:
        import memory_bank
        context = memory_bank.retrieve_context(
            f"{product.get('category') or product.get('id') or 'product'} "
            f"{getattr(job, 'geometry', 'packaging')} packaging",
            account_id=account, max_tokens=300)
    except Exception:  # noqa: BLE001 - an empty bank is a supported state
        context = ""
    return {"brand": facts, "memory": context[:1200]}


def build_brief(job: Any, *, lighting: str = DEFAULT_LIGHTING,
                camera: str = DEFAULT_CAMERA,
                background: str = DEFAULT_BACKGROUND) -> Dict[str, Any]:
    """Structured, format-aware brief handed to the local author."""
    kind = str(getattr(job, "geometry", "pouch") or "pouch").lower()
    dims = {k: v for k, v in (getattr(job, "geometry_dims", {}) or {}).items()
            if k != "require_print_dpi"}
    try:
        geo = geometry_profiles.profile(kind, **dims)
    except (KeyError, ValueError):
        geo = {"kind": kind}
    product = dict(getattr(job, "product", {}) or {})
    facts = _brand_facts(job)
    return {
        "format": kind,
        "form": FORM_NOTES.get(kind, kind),
        "geometry": {k: geo.get(k) for k in
                     ("kind", "face", "panels", "diameter_mm", "height_mm",
                      "usable_height_mm", "label_height_mm", "clearances",
                      "wrap_fraction") if k in geo},
        "product": {k: product.get(k) for k in
                    ("category", "substrate", "material_tier", "finish",
                     "environment") if product.get(k) is not None},
        "brand_facts": facts["brand"],
        "memory_context": facts["memory"],
        "lighting": lighting,
        "camera": camera,
        "background": background,
        "constraints": [
            "pristine, unprinted, blank plate",
            "no brand name, product name, net weight or legal copy",
            "no lettering, logo, emblem, badge, icon, stamp, crest or monogram",
            "describe the packaging form, material, light and background only",
            "single prompt block, under 70 words",
        ],
    }


def _clean(text: str) -> str:
    text = str(text or "").strip()
    text = re.sub(r"^```(?:json|text)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    text = text.strip().strip('"').strip("'").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:800]


def author_prompt(brief: Dict[str, Any], *, url: Optional[str] = None,
                  model: Optional[str] = None, timeout: float = 240.0) -> Dict[str, Any]:
    """Ask the local 27B for the plate prompt. Never returns a template."""
    endpoint = (url or os.environ.get("NORTHSTAR_AUTHOR_URL") or DEFAULT_URL).rstrip("/")
    model_id = model or os.environ.get("NORTHSTAR_AUTHOR_MODEL") or DEFAULT_MODEL
    body = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(brief, ensure_ascii=False)},
        ],
        "temperature": 0.2,
        "max_tokens": 1200,
        "reasoning_effort": "low",
        "stream": False,
    }
    req = urllib.request.Request(
        f"{endpoint}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise PromptAuthorUnavailable(f"local_author_unreachable: {exc}") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PromptAuthorUnavailable(f"local_author_bad_json: {exc}") from exc
    choices = payload.get("choices") or []
    message = (choices[0].get("message") or {}) if choices else {}
    finish = choices[0].get("finish_reason") if choices else None
    text = _clean(message.get("content") or "")
    if not text:
        raise PromptAuthorUnavailable("local_author_empty")
    if str(finish).lower() == "length":
        raise PromptAuthorUnavailable("local_author_truncated (raise max_tokens)")
    warnings = []
    banned = sorted(set(m.group(0).lower() for m in _BANNED.finditer(text)))
    if banned:
        warnings.append("prompt_mentions_type_terms: " + ", ".join(banned))
    if len(text.split()) > 90:
        warnings.append("prompt_over_90_words")
    return {"ok": True, "prompt": text, "model": payload.get("model") or model_id,
            "url": endpoint, "warnings": warnings, "brief": brief}


def main(argv: Optional[list] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Author a FLUX plate prompt with the local 27B.")
    ap.add_argument("--brief", default="{}", help="JSON brief")
    ap.add_argument("--url", default="")
    ap.add_argument("--model", default="")
    args = ap.parse_args(argv)
    try:
        brief = json.loads(args.brief or "{}")
        out = author_prompt(brief, url=args.url or None, model=args.model or None)
    except (PromptAuthorUnavailable, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["author_prompt", "build_brief", "PromptAuthorUnavailable",
           "DEFAULT_URL", "DEFAULT_MODEL", "SYSTEM"]
