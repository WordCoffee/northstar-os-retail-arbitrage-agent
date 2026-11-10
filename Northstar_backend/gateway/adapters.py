"""Provider adapters — one interface, several providers (blueprint §11A.1).

Every adapter returns the same shape so the gateway never branches on provider:

    {"ok": bool, "text": str|None, "bytes": bytes|None,
     "usage": {"tokens_in": int, "tokens_out": int, "gpu_seconds": float},
     "error": str|None}

Adapters are the ONLY place allowed to talk to a provider. `test_gateway.py`
fails the build if any other module imports a network client.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from gateway import roles


def _empty_usage() -> Dict[str, float]:
    return {"tokens_in": 0, "tokens_out": 0, "gpu_seconds": 0.0}


class Adapter:
    name = "base"
    network = False

    def complete(self, role: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    # ── helpers ────────────────────────────────────────────────────────────
    def _ok(self, *, role: str = "reasoning", text: Optional[str] = None,
            data: Optional[bytes] = None,
            usage: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        return {"ok": True, "text": text, "bytes": data,
                "usage": {**_empty_usage(), **(usage or {})}, "error": None,
                "provider": self.name, "model": roles.model_for(role, self.name)}

    def _fail(self, error: str) -> Dict[str, Any]:
        return {"ok": False, "text": None, "bytes": None,
                "usage": _empty_usage(), "error": error[:300],
                "provider": self.name, "model": None}


def role_of(payload: Dict[str, Any]) -> str:
    return str(payload.get("__role") or "reasoning")


class LocalOllama(Adapter):
    """The operator's own Ollama. Free, local, no key."""

    name = "local_ollama"
    network = True  # loopback only; the gateway test allowlists 127.0.0.1

    def complete(self, role, payload):
        url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
        model = roles.model_for(role, self.name) or "northstaros-qwen3.8:27b"
        try:
            import requests
            r = requests.post(f"{url}/api/generate", json={
                "model": model, "prompt": str(payload.get("prompt") or ""),
                "stream": False,
                "options": {"num_predict": int(payload.get("max_tokens") or 400)},
            }, timeout=float(payload.get("timeout") or 180))
            r.raise_for_status()
            body = r.json()
            return self._ok(role=role, text=body.get("response") or "",
                            usage={"tokens_in": int(body.get("prompt_eval_count") or 0),
                                   "tokens_out": int(body.get("eval_count") or 0)})
        except Exception as exc:  # noqa: BLE001 - an honest failure the gateway can fall back from
            return self._fail(f"{type(exc).__name__}: {exc}")


class ComfyUI(Adapter):
    """The operator's own ComfyUI for image/video. Free, local, no key."""

    name = "comfyui"
    network = True  # loopback only

    def complete(self, role, payload):
        url = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
        try:
            import requests
            stats = requests.get(f"{url}/system_stats", timeout=10)
            stats.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            return self._fail(f"comfyui unreachable: {type(exc).__name__}: {exc}")
        # The gateway does not run graphs itself: the render lane owns that. Here
        # it reports readiness and the GPU time the caller will be billed for.
        seconds = float(payload.get("gpu_seconds") or 0.0)
        return self._ok(role=role, text="comfyui ready", usage={"gpu_seconds": seconds})


class LocalVoice(Adapter):
    name = "local_voice"
    network = False

    def complete(self, role, payload):
        text = str(payload.get("prompt") or "")
        return self._ok(role=role, text=text, usage={"tokens_in": len(text) // 4})


class StubCloud(Adapter):
    """Deterministic stand-in for a cloud provider (acceptance, §11A.5).

    No network. It answers predictably so the ledger, margin and fallback can be
    asserted exactly, and it records whether the gateway passed a user and tenant.
    """

    name = "stub_cloud"
    network = False

    def complete(self, role, payload):
        if payload.get("__force_fail"):
            return self._fail("stub_cloud forced failure")
        prompt = str(payload.get("prompt") or "")
        return self._ok(
            role=role, text=f"[stub:{role}] {prompt[:120]}",
            usage={"tokens_in": max(1, len(prompt) // 4),
                   "tokens_out": max(1, len(prompt) // 8)},
        )


_REGISTRY = {a.name: a for a in (LocalOllama(), ComfyUI(), LocalVoice(), StubCloud())}


def get(name: str) -> Optional[Adapter]:
    return _REGISTRY.get(name)


def registered() -> Dict[str, bool]:
    return {k: v.network for k, v in _REGISTRY.items()}


def encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


class TransportError(RuntimeError):
    """A send attempt that never produced an HTTP response."""


def post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str],
              timeout: float):
    """One JSON POST, no retry. Lives here because this is the only module
    allowed to import a network client (test_gateway enforces it)."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - operator-configured
            return int(resp.status), resp.read(200_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return int(exc.code), (exc.read(20_000).decode("utf-8", "replace") if exc.fp else "")
    except Exception as exc:  # noqa: BLE001 - the message is scrubbed and reported, never swallowed
        raise TransportError(str(exc)) from exc
