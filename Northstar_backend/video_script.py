"""Script -> scenes: a hook, a body, a close, and durations that add up.

A duration is not a script. The sampler needs scene prompts and frame counts;
the caption lane needs short on-screen lines; the audio lane needs something to
say. This planner produces all three from the product's own copy, inside the
placement contract:

  * the beat windows are the sourced ones already recorded in
    `northstar-os-ui/src/studio/engine/hookTemplates.js` (hook 1-3 s, body
    7-20 s, CTA 2-5 s; a 3-5 word on-screen hook held about 2 s). No performance
    claim is made from those sources; the windows are structure, not lift;
  * scene durations are weighted, then the LAST scene absorbs the rounding so
    the sum is exactly the requested window and the frame counts sum to
    `round(seconds x fps)`;
  * every prompt is lower-case art direction with no digits or brand lettering,
    so it survives `text_fidelity.sanitize_brief_for_render` and the image model
    is never asked to paint words.

Local, deterministic, no model call.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional, Sequence

import video_formats

#: Published beat windows (see hookTemplates.js / reports/video_ad_structures).
#: These are structure, not a lift claim.
BEATS = (
    {"id": "hook", "weight": 0.16, "min_seconds": 2.0, "max_words": 5},
    {"id": "benefit", "weight": 0.24, "min_seconds": 2.5, "max_words": 10},
    {"id": "proof", "weight": 0.22, "min_seconds": 2.0, "max_words": 10},
    {"id": "product", "weight": 0.22, "min_seconds": 2.0, "max_words": 8},
    {"id": "cta", "weight": 0.16, "min_seconds": 2.0, "max_words": 6},
)

#: ~2.7 spoken words per second is the measured Piper pace on this box.
WORDS_PER_SECOND = 2.7
MAX_ON_SCREEN_CHARS = 28

_HOOKS = (
    "the pouch you reach for",
    "stop scrolling: {product}",
    "{weight}, one ingredient",
    "your daily {product}",
    "one ingredient, nothing to hide",
)

_STOPWORDS = {"the", "a", "an", "and", "or", "of", "to", "for", "with", "you", "your",
              "this", "that", "is", "it", "in", "on"}

_CTA = (
    "shop the pouch",
    "try it this week",
    "link in bio",
    "find it in the shop",
)

_PROMPTS = {
    "hook": ("a close-up of a hand lifting a kraft stand-up pouch from a pale studio "
             "sweep, soft diffused light, shallow depth of field, photoreal product "
             "photography"),
    "benefit": ("the pouch beside a spoon of finely milled mushroom powder on a stone "
                "surface, soft morning light, shallow depth of field, photoreal"),
    "proof": ("a macro of the powder texture and the sealed top of a kraft pouch, "
              "neutral studio light, fine detail, photoreal"),
    "product": ("the pouch standing upright on a pale seamless background, front face "
                "square to the camera, soft key light from the upper left, photoreal "
                "commercial product photography"),
    "cta": ("the pouch and a cup of coffee on a pale counter, soft window light, "
            "uncluttered space on the right, photoreal"),
}


def _words(text: str) -> List[str]:
    return [w for w in re.split(r"\s+", str(text or "").strip()) if w]


def _short(text: str, limit: int = MAX_ON_SCREEN_CHARS) -> str:
    words = _words(text)
    out = ""
    for word in words:
        trial = f"{out} {word}".strip()
        if len(trial) > limit and out:
            break
        out = trial
    return out or " ".join(words)[:limit]


def _hook_line(text: str, max_words: int = 5) -> str:
    """A complete 3-5 word hook: only a CUT phrase loses its trailing stopword."""
    words = _words(text)
    cut = words[:max_words]
    if len(words) > max_words:
        while cut and cut[-1].lower().strip(".,:;!?") in _STOPWORDS:
            cut.pop()
    return " ".join(cut) or _short(text, 24)


def _product_copy(product: Dict[str, Any]) -> Dict[str, str]:
    name = str(product.get("product") or product.get("title") or "the product").strip()
    weight = str(product.get("weight") or "").strip()
    claims = [str(c).strip() for c in (product.get("claims") or []) if str(c).strip()]
    return {
        "product": name,
        "product_lower": name.lower(),
        "weight": weight,
        "claim": claims[0] if claims else "one ingredient",
        "claim2": claims[1] if len(claims) > 1 else "",
        "subtitle": str(product.get("subtitle") or "").strip(),
    }


def _pick(options: Sequence[str], seed_text: str) -> str:
    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    return options[int(digest[:8], 16) % len(options)]


def _durations(seconds: float) -> List[float]:
    """Weighted beat durations whose sum is exactly `seconds`."""
    total_weight = sum(b["weight"] for b in BEATS)
    raw = [max(b["min_seconds"], seconds * b["weight"] / total_weight) for b in BEATS]
    # Scale down if the minimums overshoot a very short window, then make the
    # last beat absorb the residual so the sum is exact.
    scale = seconds / sum(raw)
    if scale < 1.0:
        raw = [d * scale for d in raw]
    out = [round(d, 3) for d in raw[:-1]]
    out.append(round(seconds - sum(out), 3))
    return out


def plan_scenes(product: Dict[str, Any], *, platform: str,
                seconds: Optional[float] = None,
                hook: Optional[str] = None,
                benefit: Optional[str] = None,
                proof: Optional[str] = None,
                cta: Optional[str] = None,
                seed: int = 0) -> Dict[str, Any]:
    """Plan the beats for one placement window.

    Returns scenes with start/end/seconds/frames, a text-safe render prompt, an
    on-screen line and a voiceover line, plus the sum checks the contract uses.
    """
    plan = video_formats.plan(platform, seconds)
    window = float(plan["seconds"])
    fps = int(plan["fps"])
    copy = _product_copy(product)

    hook_text = hook or _pick(_HOOKS, f"{copy['product']}|{seed}").format(
        product=copy["product_lower"], weight=copy["weight"] or "one pouch")
    episode = {
        "hook": _hook_line(hook_text),
        "benefit": _short(benefit or copy["claim"], MAX_ON_SCREEN_CHARS),
        "proof": _short(proof or copy["claim2"] or "one ingredient", MAX_ON_SCREEN_CHARS),
        "product": _short(f"{copy['weight']} {copy['subtitle']}".strip()
                          or copy["product"], MAX_ON_SCREEN_CHARS),
        "cta": _short(cta or _pick(_CTA, f"{copy['product']}|cta|{seed}"), 22),
    }
    voices = {
        "hook": hook_text,
        "benefit": benefit or f"{copy['claim']}. nothing else in the pouch.".capitalize(),
        "proof": proof or "one ingredient, milled fine and unsweetened.",
        "product": f"{copy['product']}. {copy['weight']}.".strip(),
        "cta": cta or "shop the pouch.",
    }

    durations = _durations(window)
    frames = [max(1, int(round(d * fps))) for d in durations]
    # Make frames and duration agree exactly: the largest scene absorbs the
    # residual so a stitch trim never cuts a scene in half.
    target_frames = int(plan["target_frames"])
    residual = target_frames - sum(frames)
    frames[frames.index(max(frames))] += residual
    if frames[-1] <= 0:
        raise ValueError("video_scene_too_short: the window left no frames for the close")

    scenes: List[Dict[str, Any]] = []
    cursor = 0.0
    for i, (beat, dur, count) in enumerate(zip(BEATS, durations, frames)):
        text = episode[beat["id"]]
        line = voices[beat["id"]]
        spoken_seconds = round(len(_words(line)) / WORDS_PER_SECOND, 2)
        scenes.append({
            "index": i,
            "beat": beat["id"],
            "start": round(cursor, 3),
            "end": round(cursor + count / fps, 3),
            "seconds": round(count / fps, 3),
            "frames": count,
            "prompt": _PROMPTS[beat["id"]],
            "on_screen_text": text,
            "voiceover": line,
            "voice_seconds_estimate": spoken_seconds,
            "voice_fits_scene": spoken_seconds <= (count / fps) + 0.25,
            "camera": ("push in" if beat["id"] in ("hook", "product")
                       else "slow tilt" if beat["id"] == "proof" else "hold"),
        })
        cursor += count / fps

    sum_seconds = round(sum(s["seconds"] for s in scenes), 3)
    sum_frames = sum(s["frames"] for s in scenes)
    return {
        "platform": plan["platform"],
        "aspect": plan["aspect"],
        "canvas": [plan["width"], plan["height"]],
        "fps": fps,
        "seconds": window,
        "target_frames": target_frames,
        "scenes": scenes,
        "sum_seconds": sum_seconds,
        "sum_frames": sum_frames,
        "checks": {
            "durations_sum": abs(sum_seconds - window) <= 1e-3,
            "frames_sum": sum_frames == target_frames,
            "every_scene_has_a_prompt": all(s["prompt"] for s in scenes),
            "hook_is_3_to_5_words": 3 <= len(_words(scenes[0]["on_screen_text"])) <= 5,
            "on_screen_within_limit": all(len(s["on_screen_text"]) <= 34 for s in scenes),
            "voiceover_present": all(s["voiceover"] for s in scenes),
        },
        "source_note": ("Beat windows are the sourced structure in "
                        "northstar-os-ui/src/studio/engine/hookTemplates.js "
                        "(hook 1-3 s, body 7-20 s, CTA 2-5 s; 3-5 word hook held ~2 s). "
                        "Structure only; no performance claim."),
        "compliance": plan["compliance"],
    }


__all__ = ["plan_scenes", "BEATS", "MAX_ON_SCREEN_CHARS", "WORDS_PER_SECOND"]
