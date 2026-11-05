"""Local screen companion API — the watcher, memory and voice as endpoints.

Every route here reads the operator's own desktop, so the gate is deliberately
narrow: platform admin anywhere, operator-and-above only on a non-production
box. A customer tenant role can never reach it. That mirrors the Tys Assistant
gate for the same reason.

Routes:

  GET  /api/local-screen/status              what can see/hear/speak right now
  POST /api/local-screen/sample              one watch tick (capture + OCR + store)
  POST /api/local-screen/ask                 ask about the screen, optional spoken reply
  POST /api/local-screen/watch/start|stop    the background sampler
  POST /api/local-screen/watch/pause|resume  pause without losing the thread
  GET  /api/local-screen/memory/recent|search|stats
  POST /api/local-screen/memory/purge        explicit delete (all or older than N hours)
  POST /api/local-screen/say                 speak text, returns the WAV path
  POST /api/local-screen/listen              one microphone turn -> text
  GET  /api/local-screen/audio/{name}        serve a locally synthesised WAV

Nothing here talks to a non-loopback host; the model lane enforces that itself.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import local_screen_agent as agent
import local_screen_memory as memory

try:  # pragma: no cover - import shape depends on how the app is booted
    from auth_deps import require_session as _require_session
except Exception:  # noqa: BLE001 - the app may boot without auth_deps; the route then fails closed
    async def _require_session():  # type: ignore[misc]
        return None

try:
    from foundation.authn import environment as _environment
except Exception:  # noqa: BLE001 - the environment helper is optional; default is non-production
    def _environment() -> str:  # type: ignore[misc]
        return __import__("os").environ.get("ENVIRONMENT", "").strip().lower()

router = APIRouter(prefix="/api/local-screen", tags=["local-screen"])

PLATFORM_ROLES = {"admin", "platform_admin", "super_admin"}
LOCAL_ROLES = {"operator", "owner", "admin", "platform_admin", "super_admin"}


def _role_of(user: Optional[Dict[str, Any]]) -> str:
    return str((user or {}).get("role") or "").strip().lower()


async def require_screen_operator(user: Optional[Dict[str, Any]] = Depends(_require_session)
                                  ) -> Dict[str, Any]:
    """Admit the operator on this box, or a platform admin. Never a customer."""
    if not user:
        raise HTTPException(status_code=401, detail={"code": "local_screen_auth_required"})
    role = _role_of(user)
    if role in PLATFORM_ROLES:
        return user
    if _environment() == "production":
        raise HTTPException(status_code=403, detail={"code": "local_screen_platform_admin_only"})
    if role in LOCAL_ROLES:
        return user
    raise HTTPException(status_code=403, detail={"code": "local_screen_operator_only"})


class SampleIn(BaseModel):
    vision: str = Field("auto", pattern="^(auto|always|never)$")
    scope: str = Field("active", pattern="^(active|primary|all)$")


class AskIn(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)
    speak: bool = False
    vision: str = Field("auto", pattern="^(auto|always|never)$")
    voice: Optional[str] = Field(None, max_length=80)
    scope: str = Field("active", pattern="^(active|primary|all)$")


class WatchIn(BaseModel):
    interval_s: float = Field(5.0, ge=1.0, le=3600.0)
    vision: str = Field("auto", pattern="^(auto|always|never)$")
    scope: str = Field("active", pattern="^(active|primary|all)$")


class PurgeIn(BaseModel):
    all: bool = False
    older_than_hours: Optional[float] = Field(None, gt=0, le=24 * 365)


class SayIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    voice: Optional[str] = Field(None, max_length=80)
    play: bool = True


class ListenIn(BaseModel):
    seconds: float = Field(6.0, ge=1.0, le=60.0)
    engine: str = Field("auto", pattern="^(auto|whisper|sapi)$")


@router.get("/status")
def screen_status(_user: Dict[str, Any] = Depends(require_screen_operator)):
    return agent.status()


@router.post("/sample")
def screen_sample(body: SampleIn, _user: Dict[str, Any] = Depends(require_screen_operator)):
    out = agent.sample(vision=body.vision, scope=body.scope)
    if not out.get("ok"):
        raise HTTPException(status_code=503,
                            detail={"code": "screen_capture_failed",
                                    "error": out.get("error")})
    return out


@router.post("/ask")
def screen_ask(body: AskIn, _user: Dict[str, Any] = Depends(require_screen_operator)):
    out = agent.ask(body.question, speak=body.speak, voice=body.voice, vision=body.vision,
                     scope=body.scope)
    if not out.get("ok"):
        raise HTTPException(status_code=502,
                            detail={"code": "screen_answer_failed",
                                    "error": out.get("error")})
    return out


@router.post("/watch/start")
def watch_start(body: WatchIn, _user: Dict[str, Any] = Depends(require_screen_operator)):
    out = agent.WATCHER.start(interval_s=body.interval_s, vision=body.vision,
                             scope=body.scope)
    agent.WATCHER.resume()
    return {"started": True, **out}


@router.post("/watch/stop")
def watch_stop(_user: Dict[str, Any] = Depends(require_screen_operator)):
    return agent.WATCHER.stop("api")


@router.post("/watch/pause")
def watch_pause(_user: Dict[str, Any] = Depends(require_screen_operator)):
    return agent.WATCHER.pause()


@router.post("/watch/resume")
def watch_resume(_user: Dict[str, Any] = Depends(require_screen_operator)):
    return agent.WATCHER.resume()


@router.get("/memory/recent")
def memory_recent(limit: int = Query(20, ge=1, le=200),
                  minutes: Optional[float] = Query(None, gt=0),
                  _user: Dict[str, Any] = Depends(require_screen_operator)):
    return memory.recent(limit=limit, since_minutes=minutes)


@router.get("/memory/search")
def memory_search(q: str = Query(..., min_length=1, max_length=200),
                  limit: int = Query(20, ge=1, le=200),
                  minutes: Optional[float] = Query(None, gt=0),
                  _user: Dict[str, Any] = Depends(require_screen_operator)):
    return memory.search(q, limit=limit, since_minutes=minutes)


@router.get("/memory/stats")
def memory_stats(_user: Dict[str, Any] = Depends(require_screen_operator)):
    return memory.stats()


@router.post("/memory/purge")
def memory_purge(body: PurgeIn, _user: Dict[str, Any] = Depends(require_screen_operator)):
    if not body.all and body.older_than_hours is None:
        raise HTTPException(status_code=422,
                            detail={"code": "purge_scope_required",
                                    "hint": "set all=true or older_than_hours"})
    before = None
    if body.older_than_hours is not None:
        import time
        before = time.time() - body.older_than_hours * 3600
    return memory.purge(all=body.all, before=before)


@router.post("/say")
def screen_say(body: SayIn, _user: Dict[str, Any] = Depends(require_screen_operator)):
    try:
        out = agent.say(body.text, voice=body.voice)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503,
                            detail={"code": "voice_unavailable", "error": str(exc)[:300]})
    out["url"] = f"/api/local-screen/audio/{out['name']}"
    if body.play:
        out["played"] = agent.play(out["file"]).get("played", False)
    return out


@router.post("/listen")
def screen_listen(body: ListenIn, _user: Dict[str, Any] = Depends(require_screen_operator)):
    import local_ear
    out = local_ear.listen_once(body.seconds, engine=body.engine)
    if not out.get("ok"):
        raise HTTPException(status_code=503,
                            detail={"code": "listen_failed", **{k: v for k, v in out.items()
                                                                if k != "ok"}})
    return out


_AUDIO_NAME = re.compile(r"^[A-Za-z0-9._-]+\.wav$")


@router.get("/audio/{name}")
def screen_audio(name: str, _user: Dict[str, Any] = Depends(require_screen_operator)):
    if not _AUDIO_NAME.match(name):
        raise HTTPException(status_code=400, detail="bad audio name")
    path = Path(agent.AUDIO_DIR) / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="audio not found")
    return FileResponse(str(path), media_type="audio/wav", filename=name)
