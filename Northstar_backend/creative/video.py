"""Cloud video generation (fal: Wan / Kling / Veo) — GATED and in scope.

Video is real money per second, so it is built but never runs unless the fal key
is present **and** ``MEDIA_GEN_LIVE=1``. Cost is estimated from
``docs/CREATIVE_MEDIA_STACK.md`` rates. Watermarked providers are flagged so the
caller can disclose AI generation where required.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from . import cloud

VIDEO_MODELS: Dict[str, Dict[str, Any]] = {
    "wan-2.5": {"fal": "fal-ai/wan-2.5", "cost_per_s": 0.05, "max_s": 15,
                "note": "budget motion"},
    "flux-3-draft": {"fal": "fal-ai/flux-3/draft", "cost_per_s": 0.06, "free_per_day": 5,
                     "note": "fast iteration / storyboards"},
    "kling-2.6-pro": {"fal": "fal-ai/kling-video/v2.6/pro", "cost_per_s": 0.07,
                      "cost_per_s_audio": 0.14, "max_s": 15,
                      "note": "UGC / shorts with real people + native audio"},
    "kling-v3-i2v": {"fal": "fal-ai/kling-video/v3", "cost_per_s": 0.112,
                     "note": "image->video product shots"},
    "veo-3.1-fast": {"fal": "fal-ai/veo-3.1/fast", "cost_per_s": 0.10,
                     "watermark": "SynthID", "note": "hero-quality premium ads"},
}


def video_catalog() -> Dict[str, Any]:
    return {
        "models": {k: {kk: vv for kk, vv in v.items() if kk != "fal"} for k, v in VIDEO_MODELS.items()},
        "currency": "USD",
        "basis": "docs/CREATIVE_MEDIA_STACK.md (Sept-2026 list rates)",
    }


def estimate_video_cost(model: str, seconds: float, *, audio: bool = False) -> Optional[float]:
    m = VIDEO_MODELS.get(model)
    if not m:
        return None
    rate = m.get("cost_per_s_audio", m["cost_per_s"]) if audio else m["cost_per_s"]
    return round(rate * float(seconds), 4)


def build_video_request(model: str, prompt: str, *, image_url: Optional[str] = None,
                        duration: int = 5, aspect: str = "9:16") -> Dict[str, Any]:
    """Pure builder — the exact fal payload for a video job (unit-testable)."""
    m = VIDEO_MODELS.get(model)
    if not m:
        raise ValueError(f"unknown video model '{model}'")
    payload: Dict[str, Any] = {"prompt": prompt, "duration": int(duration), "aspect_ratio": aspect}
    if image_url:
        payload["image_url"] = image_url
    return {"url": f"https://fal.run/{m['fal']}", "payload": payload, "model": model}


def generate_video(model: str, prompt: str, *, image_url: Optional[str] = None,
                   duration: int = 5, aspect: str = "9:16") -> Dict[str, Any]:
    """Estimate + (gated) submit a video job. Never runs unless armed."""
    cost = estimate_video_cost(model, duration)
    cloud.require_armed("fal")
    req = build_video_request(model, prompt, image_url=image_url, duration=duration, aspect=aspect)
    result = cloud._post_json(req["url"], req["payload"], cloud._auth_headers("fal"),
                              timeout=600.0)
    return {
        "provider": "fal", "model": model, "cost_estimate": cost,
        "watermark": VIDEO_MODELS[model].get("watermark"),
        "result": result, "basis": "cloud video call (armed)",
        "disclosure": "AI-generated video" + (" (watermarked)" if VIDEO_MODELS[model].get("watermark") else ""),
    }
