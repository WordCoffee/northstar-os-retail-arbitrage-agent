"""Cloud media generation clients (fal / OpenRouter / Replicate) — GATED.

Local is the default lane. Cloud generation runs only when the provider key is
present **and** ``MEDIA_GEN_LIVE=1``. Not armed → ``ProviderUnavailable`` (never a
silent fallback, never a fake success). No key value is ever read or returned.

The HTTP shapes mirror each provider's documented endpoint; the calls are only
executed when armed, so a missing key can never spend money.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from . import providers


class ProviderUnavailable(RuntimeError):
    pass


# Per-image list rates (USD) from shared/model-suite.json (planning values).
IMAGE_COST: Dict[str, float] = {
    "flux.2-klein-9b": 0.015,
    "flux.2-pro": 0.03,
    "flux.2-pro-edit": 0.055,
    "gpt-image-2-low": 0.03,
    "gpt-image-2-high": 0.18,
    "nano-banana-2": 0.08,
}
# Provider model ids often hyphenate the family (flux-2-pro); accept both forms.
_IMAGE_COST_ALIASES = {k.replace(".", "-"): v for k, v in IMAGE_COST.items()}

DEFAULT_MODELS: Dict[str, str] = {
    "fal": "fal-ai/flux-2-pro",
    "openrouter": "openai/gpt-image-2",
    "replicate": "black-forest-labs/flux-2-pro",
}


def _http(url: str, *, method: str = "GET", payload: Optional[dict] = None,
          headers: Optional[Dict[str, str]] = None, timeout: float = 120.0) -> bytes:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    h = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _post_json(url: str, payload: dict, headers: Dict[str, str], timeout: float = 120.0) -> Any:
    return json.loads(_http(url, method="POST", payload=payload, headers=headers,
                            timeout=timeout).decode("utf-8"))


def require_armed(provider: str) -> None:
    if not providers.cloud_armed(provider):
        raise ProviderUnavailable(
            f"cloud provider '{provider}' is not armed "
            f"(needs its API key present and MEDIA_GEN_LIVE=1)"
        )


def estimate_cost(provider: str, model: Optional[str] = None) -> Optional[float]:
    key = (model or DEFAULT_MODELS.get(provider, "")).split("/")[-1]
    return IMAGE_COST.get(key, _IMAGE_COST_ALIASES.get(key))


def build_request(provider: str, prompt: str, *, model: Optional[str] = None,
                  image_size: str = "1024x1024", num_images: int = 1) -> Dict[str, Any]:
    """Pure builder — the exact request payload for a provider (unit-testable)."""
    model = model or DEFAULT_MODELS.get(provider, "")
    if provider == "fal":
        return {"url": f"https://fal.run/{model}",
                "payload": {"prompt": prompt, "image_size": image_size,
                            "num_images": num_images}}
    if provider == "openrouter":
        return {"url": "https://openrouter.ai/api/v1/images/generations",
                "payload": {"model": model, "prompt": prompt, "n": num_images,
                            "size": image_size}}
    if provider == "replicate":
        return {"url": "https://api.replicate.com/v1/predictions",
                "payload": {"input": {"prompt": prompt, "num_outputs": num_images}}}
    raise ProviderUnavailable(f"unknown provider '{provider}'")


def _extract_image_urls(provider: str, result: Any) -> list[str]:
    if not isinstance(result, dict):
        return []
    if provider == "fal":
        imgs = result.get("images") or []
        return [i.get("url") for i in imgs if isinstance(i, dict) and i.get("url")]
    if provider == "openrouter":
        data = result.get("data") or []
        return [d.get("url") for d in data if isinstance(d, dict) and d.get("url")]
    if provider == "replicate":
        out = result.get("output")
        if isinstance(out, str):
            return [out]
        if isinstance(out, list):
            return [u for u in out if isinstance(u, str)]
    return []


def _auth_headers(provider: str) -> Dict[str, str]:
    cfg = providers.CLOUD_PROVIDERS[provider]
    key = os.environ.get(cfg["env"], "")
    if provider == "fal":
        return {"Authorization": f"Key {key}"}
    if provider == "replicate":
        return {"Authorization": f"Bearer {key}", "Prefer": "wait"}
    return {"Authorization": f"Bearer {key}"}


def generate(prompt: str, provider: str, out_path: str | os.PathLike, *,
             model: Optional[str] = None, image_size: str = "1024x1024",
             num_images: int = 1) -> Dict[str, Any]:
    """Generate an image on a cloud provider. Gated by the arming policy."""
    require_armed(provider)
    req = build_request(provider, prompt, model=model, image_size=image_size,
                        num_images=num_images)
    result = _post_json(req["url"], req["payload"], _auth_headers(provider))
    urls = _extract_image_urls(provider, result)
    if not urls:
        raise ProviderUnavailable(f"{provider} returned no image: {str(result)[:200]}")
    data = _http(urls[0], timeout=180.0)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    return {
        "provider": provider,
        "model": model or DEFAULT_MODELS.get(provider),
        "output": str(out),
        "cost_estimate": estimate_cost(provider, model),
        "basis": "cloud provider call (armed)",
    }
