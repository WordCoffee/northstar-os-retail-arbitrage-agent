"""Live write clients for approved write actions — credential-gated.

These are the real publish / spend clients behind the approval workflow. They run
only when (a) the request is approved, (b) its write flag is armed, and (c) the
required provider credential is present. Any missing piece raises
``WriteUnavailable`` (never a fake success, never a silent skip).

Credential values are used only in-process to authenticate and are never read,
returned, logged, or surfaced. ``*_ready()`` helpers are presence-only.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Dict, List, Optional


class WriteUnavailable(RuntimeError):
    def __init__(self, message: str, missing: Optional[List[str]] = None):
        super().__init__(message)
        self.missing = missing or []


SOCIAL_PLATFORMS: Dict[str, Dict[str, str]] = {
    "instagram": {"token_env": "INSTAGRAM_ACCESS_TOKEN"},
    "facebook": {"token_env": "META_ACCESS_TOKEN"},
    "x": {"token_env": "X_ACCESS_TOKEN"},
    "tiktok": {"token_env": "TIKTOK_ACCESS_TOKEN"},
    "linkedin": {"token_env": "LINKEDIN_ACCESS_TOKEN"},
}

ADS_ENVS: List[str] = [
    "AMAZON_ADS_REFRESH_TOKEN",
    "AMAZON_ADS_CLIENT_ID",
    "AMAZON_ADS_CLIENT_SECRET",
]


def _present(name: str) -> bool:
    return bool(str(os.environ.get(name, "") or "").strip())


def social_ready(platform: str) -> bool:
    cfg = SOCIAL_PLATFORMS.get(platform)
    return bool(cfg and _present(cfg["token_env"]))


def ads_ready() -> bool:
    return all(_present(n) for n in ADS_ENVS)


def social_platforms_status() -> Dict[str, Any]:
    return {p: {"token_env": c["token_env"], "present": _present(c["token_env"])}
            for p, c in SOCIAL_PLATFORMS.items()}


def ads_status() -> Dict[str, Any]:
    return {"envs": {n: _present(n) for n in ADS_ENVS}, "ready": ads_ready()}


# --- pure request builders (unit-testable, no network) ---------------------

def build_social_request(platform: str, post: Dict[str, Any]) -> Dict[str, Any]:
    if platform not in SOCIAL_PLATFORMS:
        raise WriteUnavailable(f"unknown platform '{platform}'", ["platform"])
    text = post.get("text") or post.get("caption", "")
    if platform == "x":
        return {"url": "https://api.x.com/2/tweets", "payload": {"text": text[:280]}}
    if platform == "instagram":
        return {"url": "https://graph.facebook.com/v21.0/me/media",
                "payload": {"caption": text, "image_url": post.get("image_url")}}
    if platform == "facebook":
        return {"url": "https://graph.facebook.com/v21.0/me/feed",
                "payload": {"message": text, "link": post.get("link")}}
    if platform == "linkedin":
        return {"url": "https://api.linkedin.com/v2/ugcPosts",
                "payload": {"author": post.get("author", ""), "text": text}}
    return {"url": "https://open.tiktokapis.com/v2/post/publish/", "payload": {"caption": text}}


def build_ads_request(change: Dict[str, Any]) -> Dict[str, Any]:
    return {"url": "https://advertising-api.amazon.com/sp/campaigns", "payload": change}


# --- live calls (credential-gated) ----------------------------------------

def _post(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: float = 60.0) -> Any:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return {"status": resp.status, "body": resp.read().decode("utf-8", "replace")[:400]}


def publish(platform: str, post: Dict[str, Any]) -> Dict[str, Any]:
    cfg = SOCIAL_PLATFORMS.get(platform)
    if not cfg:
        raise WriteUnavailable(f"unknown platform '{platform}'", ["platform"])
    if not _present(cfg["token_env"]):
        raise WriteUnavailable("social publish not configured", [cfg["token_env"]])
    req = build_social_request(platform, post)
    out = _post(req["url"], req["payload"],
                {"Authorization": f"Bearer {os.environ[cfg['token_env']]}"})
    return {"published": True, "platform": platform, **out}


def ads_write(change: Dict[str, Any]) -> Dict[str, Any]:
    missing = [n for n in ADS_ENVS if not _present(n)]
    if missing:
        raise WriteUnavailable("ads write not configured", missing)
    req = build_ads_request(change)
    out = _post(req["url"], req["payload"], {
        "Authorization": f"Bearer {os.environ[ADS_ENVS[0]]}",
        "Amazon-Advertising-API-ClientId": os.environ[ADS_ENVS[1]],
    })
    return {"applied": True, **out}
