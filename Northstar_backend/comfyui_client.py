"""ComfyUI API client + orchestrator scaffold (localhost-only, no cloud).

The suite uses ComfyUI as the engine: the planner builds a *job plan*, and this
client submits **workflow templates** to a running ComfyUI over its HTTP API
(``/prompt``, ``/history``, ``/queue``, ``/interrupt``). It does not invent
graphs — templates come from ComfyUI's own template library or a local
``creative_workflows/`` directory.

It never contacts a cloud provider and never generates anything by itself; it
only queues work on the operator's own localhost ComfyUI (which is the arming
gate's domain).
"""
from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

DEFAULT_URL = "http://127.0.0.1:8188"


class ComfyUIError(RuntimeError):
    pass


def _join(base: str, path: str) -> str:
    return base.rstrip("/") + path


def reachable(base: str = DEFAULT_URL, timeout: float = 0.3) -> str:
    """reachable | unreachable | unknown — bounded localhost probe."""
    try:
        p = urlparse(base)
        host, port = p.hostname, p.port or 80
        if not host:
            return "unknown"
        with socket.create_connection((host, int(port)), timeout=timeout):
            return "reachable"
    except (OSError, ValueError):
        return "unreachable"


def extract_images(history_entry: Dict) -> List[str]:
    """Pull output image/video filenames from a /history entry. Pure."""
    out: List[str] = []
    for node in (history_entry or {}).get("outputs", {}).values():
        for key in ("images", "gifs", "videos"):
            for item in node.get(key, []) or []:
                fn = item.get("filename") if isinstance(item, dict) else item
                if fn:
                    out.append(fn)
    return out


def load_template(path: Path) -> Dict:
    """Load a ComfyUI workflow template (API format) from disk. Never invents one."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ComfyUIError(f"template not readable: {path} ({e})") from e


class ComfyUIClient:
    """Minimal localhost ComfyUI client (urllib only; no new deps)."""

    def __init__(self, base_url: str = DEFAULT_URL, timeout: float = 30.0):
        self.base = base_url.rstrip("/")
        self.timeout = timeout

    def reachable(self) -> str:
        return reachable(self.base)

    def _get(self, path: str, timeout: Optional[float] = None):
        with urllib.request.urlopen(_join(self.base, path), timeout=timeout or self.timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def _post(self, path: str, body: Optional[Dict] = None, timeout: Optional[float] = None):
        data = json.dumps(body or {}).encode("utf-8")
        req = urllib.request.Request(_join(self.base, path), data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw) if raw else {}

    def system_stats(self) -> Dict:
        return self._get("/system_stats", timeout=10.0)

    def queue(self) -> Dict:
        return self._get("/queue")

    def submit(self, workflow: Dict, client_id: Optional[str] = None) -> str:
        body = {"prompt": workflow}
        if client_id:
            body["client_id"] = client_id
        res = self._post("/prompt", body)
        pid = res.get("prompt_id")
        if not pid:
            raise ComfyUIError(f"submit failed: {res}")
        return pid

    def history(self, prompt_id: str) -> Dict:
        return self._get(f"/history/{prompt_id}")

    def wait(self, prompt_id: str, timeout: float = 900.0, poll: float = 2.0) -> Dict:
        """Poll /history until outputs appear or timeout. Returns the entry."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            hist = self.history(prompt_id)
            entry = hist.get(prompt_id) if isinstance(hist, dict) else None
            if entry and entry.get("outputs"):
                return entry
            time.sleep(poll)
        raise ComfyUIError(f"timed out waiting for {prompt_id}")

    def interrupt(self) -> Dict:
        return self._post("/interrupt", {})

    def free(self, unload_models: bool = True, free_memory: bool = True) -> Dict:
        """Ask ComfyUI to unload models / free VRAM (between stages)."""
        return self._post("/free", {"unload_models": unload_models, "free_memory": free_memory})
