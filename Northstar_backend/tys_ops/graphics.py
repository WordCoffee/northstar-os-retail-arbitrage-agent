"""FLUX 3 graphics lane — direct, no ComfyUI.

The operator's routing rule: visual work runs on FLUX 3 and nothing else. So
this module talks to a **standalone FLUX 3 endpoint**, never to ComfyUI, and it
never falls back to another model when FLUX 3 is not ready. A missing endpoint
or missing weights is a blocked step with a stable code — not a silent
substitution.

GPU discipline:

* FLUX 3 needs the whole card, so before a render the lane suspends the
  competing engines — the MoE coding worker on ``:8080`` and any Ollama model
  resident on ``:11434`` — then takes the same cross-process GPU lock the render
  lanes use. Acquiring/creating that lock does not start ComfyUI.
* Nothing here starts ComfyUI, and nothing here starts the coding worker. The
  coding lane restarts its worker on demand, after the render.

Endpoint contract (``FLUX3_SERVER_URL``, default ``http://127.0.0.1:8190``)::

    POST /generate
      {"prompt": str, "width": int, "height": int, "steps": int,
       "seed": int|null, "model": "flux-3-image-klein"}
    ->  {"path": str} | {"image_b64": str} | {"images": [ ... ]}

    GET /health -> {"status": "ok", "model": "..."} (anything 2xx is accepted)
"""

from __future__ import annotations

import base64
import json
import os
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

DEFAULT_URL = os.environ.get("FLUX3_SERVER_URL", "http://127.0.0.1:8190")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
CODING_PORT = int(os.environ.get("TYS_CODING_PORT", "8080"))
MODEL_ID = os.environ.get("FLUX3_MODEL_ID", "flux-3-image-klein")

#: Defaults match the installed FLUX 3 bundle (see tools/flux3_gateway.py).
DEFAULT_UNET = os.environ.get("FLUX3_UNET") or "flux3-image-klein-nvfp4.safetensors"
DEFAULT_TEXT_ENCODER = (os.environ.get("FLUX3_TEXT_ENCODER")
                        or "qwen3vl_4b_int8_convrot.safetensors")
DEFAULT_VAE = os.environ.get("FLUX3_VAE") or "flux2-vae.safetensors"
MODELS_ROOT = os.environ.get("COMFYUI_MODELS") or r"C:\Users\T2Hol\ComfyUI\models"

#: Processes the suspension step must never touch.
_PROTECTED = ("comfy", "uvicorn", "northstar", "chrome", "python -m uvicorn")


class GraphicsError(RuntimeError):
    """Stable refusal from the graphics lane."""

    def __init__(self, code: str, detail: str = "", **extra: Any):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail
        self.extra = extra

    def as_dict(self) -> Dict[str, Any]:
        out = {"code": self.code, "detail": self.detail}
        out.update(self.extra)
        return out


def _base() -> str:
    return (os.environ.get("FLUX3_SERVER_URL") or DEFAULT_URL).rstrip("/")


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def weights_present() -> Dict[str, Any]:
    """FLUX 3 needs all three files; a half-installed model is not installed."""
    keys = {
        "model": (os.environ.get("STUDIO_FLUX3_MODEL") or DEFAULT_UNET,
                  "diffusion_models"),
        "text_encoder": (os.environ.get("STUDIO_FLUX3_TEXT_ENCODER") or DEFAULT_TEXT_ENCODER,
                         "text_encoders"),
        "vae": (os.environ.get("STUDIO_FLUX3_VAE") or DEFAULT_VAE, "vae"),
    }
    missing: List[str] = []
    paths: Dict[str, str] = {}
    for name, (value, folder) in keys.items():
        path = value if os.path.isabs(value) else os.path.join(MODELS_ROOT, folder, value)
        paths[name] = path
        if not os.path.isfile(path):
            missing.append(name)
    return {"present": not missing, "missing": missing, "paths": paths}


def status(timeout: float = 0.6) -> Dict[str, Any]:
    """Availability of the graphics lane, without touching ComfyUI."""
    url = _base()
    host = url.split("://", 1)[-1].split("/")[0]
    hostname, _, port_text = host.partition(":")
    port = int(port_text or ("443" if url.startswith("https") else "80"))
    listening = _port_open(hostname or "127.0.0.1", port, timeout)
    weights = weights_present()
    healthy = False
    detail = ""
    if listening:
        try:
            with urllib.request.urlopen(url + "/health", timeout=timeout) as response:
                healthy = 200 <= int(response.status) < 300
        except Exception as exc:  # noqa: BLE001 - availability is a report, not a crash
            detail = f"{type(exc).__name__}: {exc}"

    available = bool(listening and healthy and weights["present"])
    if available:
        reason = "flux3 endpoint healthy"
    elif not weights["present"]:
        reason = ("flux3_weights_not_installed: missing "
                  + ", ".join(weights["missing"]))
    elif not listening:
        reason = f"flux3_endpoint_unreachable: nothing listening at {url}"
    else:
        reason = f"flux3_endpoint_unhealthy: {detail or 'no healthy /health response'}"

    return {
        "adapter": "graphics",
        "engine": "flux3",
        "model": MODEL_ID,
        "endpoint": url,
        "available": bool(available),
        "weights": weights,
        "listening": listening,
        "healthy": healthy,
        "detail": reason,
    }


def _post(path: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(_base() + path, data=body,
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        text = ""
        try:
            text = exc.read().decode("utf-8", "replace")[:400]
        except Exception:
            pass
        raise GraphicsError("flux3_http_error", f"{exc.code} {exc.reason}: {text}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise GraphicsError("flux3_request_failed", f"{type(exc).__name__}: {exc}")
    except json.JSONDecodeError:
        raise GraphicsError("flux3_bad_response", "the endpoint did not return JSON")


def generate(prompt: str, *, width: int = 1024, height: int = 1024,
             steps: int = 28, seed: Optional[int] = None,
             timeout: float = 600.0,
             reference_image: Optional[bytes] = None) -> Dict[str, Any]:
    """Render one image on FLUX 3. No fallback, no ComfyUI."""
    prompt = (prompt or "").strip()
    if not prompt:
        raise GraphicsError("prompt_required", "a graphics step needs a prompt")
    ready = status()
    if not ready["available"]:
        raise GraphicsError("flux3_unavailable", ready["detail"], status=ready)

    payload = {
        "prompt": prompt,
        "width": int(width),
        "height": int(height),
        "steps": int(steps),
        "seed": None if seed is None else int(seed),
        "model": MODEL_ID,
    }
    if reference_image:
        payload["reference_image"] = base64.b64encode(reference_image).decode("ascii")
    raw = _post("/generate", payload, timeout)
    artifacts: List[str] = []
    if isinstance(raw.get("images"), list):
        for item in raw["images"]:
            if isinstance(item, str):
                artifacts.append(item)
            elif isinstance(item, dict):
                for key in ("path", "file", "url"):
                    if item.get(key):
                        artifacts.append(str(item[key]))
                        break
    for key in ("path", "file", "url", "output"):
        if raw.get(key):
            artifacts.append(str(raw[key]))
    image_b64 = raw.get("image_b64") or raw.get("b64")
    if image_b64 and not artifacts:
        # Persist beside the other generated media, never inside the repo root.
        target_dir = os.environ.get("TYS_GRAPHICS_OUT", "").strip()
        if not target_dir:
            target_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "..", "data", "tys", "graphics")
        os.makedirs(target_dir, exist_ok=True)
        name = f"flux3-{int(time.time())}-{abs(hash(prompt)) % 100000}.png"
        path = os.path.abspath(os.path.join(target_dir, name))
        with open(path, "wb") as handle:
            handle.write(base64.b64decode(image_b64))
        artifacts.append(path)

    if not artifacts:
        raise GraphicsError("flux3_no_artifact",
                            "endpoint answered without a path or image payload",
                            response=str(raw)[:400])
    return {
        "engine": "flux3",
        "model": MODEL_ID,
        "prompt": prompt,
        "width": int(width),
        "height": int(height),
        "steps": int(steps),
        "seed": payload["seed"],
        "mode": "reference" if reference_image else "text",
        "artifacts": artifacts,
        "raw": {k: v for k, v in raw.items() if k not in ("image_b64", "b64")},
    }


# ---------------------------------------------------------------------------
# Engine suspension before a render
# ---------------------------------------------------------------------------

def _ollama_loaded() -> List[str]:
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/ps", timeout=3) as response:
            data = json.loads(response.read().decode("utf-8") or "{}")
        return [str(m.get("name")) for m in data.get("models") or [] if m.get("name")]
    except Exception:
        return []


def _unload_ollama() -> List[str]:
    unloaded: List[str] = []
    for name in _ollama_loaded():
        try:
            request = urllib.request.Request(
                OLLAMA_URL + "/api/generate",
                data=json.dumps({"model": name, "keep_alive": 0}).encode("utf-8"),
                headers={"Content-Type": "application/json"})
            urllib.request.urlopen(request, timeout=20).read()
            unloaded.append(name)
        except Exception:
            continue
    return unloaded


def _stop_coding_worker() -> str:
    """Stop the MoE coding worker if (and only if) it is the one listening."""
    pid = _listening_pid(CODING_PORT)
    if not pid:
        return "nothing_listening"
    name = _process_name(pid).lower()
    if any(token in name for token in _PROTECTED):
        return f"refused_protected_process:{name or pid}"
    try:
        import psutil  # type: ignore

        proc = psutil.Process(pid)
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except Exception:
            proc.kill()
        return f"stopped pid {pid}"
    except Exception:
        # No psutil: use taskkill by pid, still pid-scoped, never by name.
        try:
            import subprocess

            result = subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                                    capture_output=True, text=True, timeout=30)
            return (f"stopped pid {pid}" if result.returncode == 0
                    else f"stop_failed: {result.stderr.strip()[:200]}")
        except Exception as exc:  # noqa: BLE001
            return f"stop_failed: {exc}"


def _listening_pid(port: int) -> Optional[int]:
    try:
        import psutil  # type: ignore

        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port == port and conn.status == "LISTEN":
                return conn.pid
    except Exception:
        pass
    try:
        import subprocess

        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-NetTCPConnection -State Listen -LocalPort {int(port)} "
             f"-ErrorAction SilentlyContinue | Select-Object -First 1 "
             f"-ExpandProperty OwningProcess)"],
            capture_output=True, text=True, timeout=20).stdout.strip()
        return int(out) if out.isdigit() else None
    except Exception:
        return None


def _process_name(pid: int) -> str:
    try:
        import psutil  # type: ignore

        return psutil.Process(pid).name()
    except Exception:
        try:
            import subprocess

            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue).Name"],
                capture_output=True, text=True, timeout=20).stdout.strip()
            return out
        except Exception:
            return ""


def suspend_competing_engines() -> Dict[str, Any]:
    """Free the card for FLUX 3: unload Ollama and stop the coding worker.

    ComfyUI, Chrome and the backend are never touched.
    """
    unloaded = _unload_ollama()
    worker = _stop_coding_worker()
    return {"ollama_unloaded": unloaded, "coding_worker": worker,
            "protected": list(_PROTECTED)}


def gpu_lock():
    """The box's one cross-process GPU lock. Acquiring it starts nothing."""
    try:
        import studio_generation as sg  # noqa: WPS433

        getter = getattr(sg, "gpu_lock", None)
        if callable(getter):
            return getter()
        return getattr(sg, "_RENDER_LOCK", None)
    except Exception:
        return None
