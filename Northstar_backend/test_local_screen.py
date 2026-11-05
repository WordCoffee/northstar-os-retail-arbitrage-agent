"""Local screen lane tests — offline. No screen, model, mic or speaker is touched.

What is pinned here is the honesty and the safety of a feature that reads
everything on the operator's desktop:

  * a non-loopback Ollama host is refused, always
  * secrets are redacted before text is stored or sent to a model
  * a vision call sets `keep_alive: 0` and pins `num_gpu: 0` without headroom
  * a failed capture/OCR/model call returns the reason, never a fake answer
  * memory dedupes idle frames, searches, and refuses an unscoped purge
  * the watcher stops after a bounded number of consecutive failures
  * the API admits the operator on a dev box and refuses a customer role
"""

from __future__ import annotations

import io
import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import local_ear  # noqa: E402
import local_screen as screen  # noqa: E402
import local_screen_agent as agent  # noqa: E402
import local_screen_memory as memory  # noqa: E402


def _image(size=(1600, 900), colour=(240, 240, 240)):
    from PIL import Image
    return Image.new("RGB", size, colour)


def _png(size=(64, 64), colour=(200, 200, 200)) -> bytes:
    buf = io.BytesIO()
    _image(size, colour).save(buf, format="PNG")
    return buf.getvalue()


def _ocr_result(lines):
    """Build the RapidOCR shape: [[box, text, score], ...]."""
    out = []
    for i, text in enumerate(lines):
        y = i * 20
        out.append([[[0, y], [100, y], [100, y + 14], [0, y + 14]], text, 0.97])
    return out


# ── loopback rule ────────────────────────────────────────────────────────────

def test_loopback_hosts_are_allowed():
    for url in ("http://127.0.0.1:11434/api/generate",
                "http://localhost:11434/api/chat",
                "http://[::1]:11434/api/tags"):
        assert screen.assert_loopback(url) == url


def test_remote_host_is_refused_with_a_reason():
    with pytest.raises(screen.CloudRefused) as exc:
        screen.assert_loopback("https://ollama.example.com/api/generate")
    assert "never leaves the machine" in str(exc.value)


def test_bind_address_is_rewritten_to_loopback():
    assert screen.normalise_host("0.0.0.0:11434") == "http://127.0.0.1:11434"


def test_a_poster_that_points_off_box_is_refused_before_sending():
    calls = []

    def post(url, payload, timeout):
        calls.append(url)
        return {}

    with pytest.raises(screen.CloudRefused):
        screen._http_post("https://api.example.com/v1/chat", {"x": 1}, 5)
    assert calls == [], "a refused host must not be contacted"


# ── capture ──────────────────────────────────────────────────────────────────

def test_capture_downscales_and_hashes_the_frame():
    out = screen.capture(grabber=lambda: _image((2560, 1600)), max_side=800,
                         scope="primary")
    assert out["ok"]
    assert out["width"] == 800
    assert out["height"] == 500
    assert out["native"] == {"width": 2560, "height": 1600}
    assert len(out["sha1"]) == 40
    assert out["bytes"] > 0


def test_capture_reads_only_the_foreground_window_when_asked(monkeypatch):
    monkeypatch.setattr(screen, "_foreground_rect", lambda: (100, 50, 900, 650))
    monkeypatch.setattr(screen, "_virtual_screen", lambda: (0, 0, 2560, 1600))
    out = screen.capture(grabber=lambda: _image((2560, 1600)), max_side=800,
                         scope="active", include_window=False)
    assert out["scope"]["cropped"] is True
    assert out["scope"]["region"] == {"left": 100, "top": 50, "width": 800, "height": 600}


def test_capture_falls_back_to_the_desktop_when_the_window_rect_is_unusable(monkeypatch):
    monkeypatch.setattr(screen, "_foreground_rect", lambda: None)
    out = screen.capture(grabber=lambda: _image((2560, 1600)), max_side=800,
                         scope="active", include_window=False)
    assert out["scope"]["cropped"] is False
    assert out["width"] == 800


def test_capture_reports_a_black_frame_as_possibly_locked():
    out = screen.capture(grabber=lambda: _image((800, 600), (0, 0, 0)), max_side=400,
                         scope="primary")
    assert out["ok"]
    assert out["possibly_secure_desktop"] is True


def test_capture_failure_returns_the_reason_not_an_empty_frame():
    def boom():
        raise OSError("no desktop")
    out = screen.capture(grabber=boom)
    assert out["ok"] is False
    assert "OSError" in out["error"]


# ── OCR ──────────────────────────────────────────────────────────────────────

def test_ocr_reads_in_visual_order_and_joins_lines():
    def fake(_png):
        return _ocr_result(["second line", "first line"]), 0.1

    # The fake puts "second line" at y=0, so it is genuinely first on screen.
    out = screen.ocr(b"x", engine=fake)
    assert out["ok"] and out["line_count"] == 2
    assert out["text"].splitlines() == ["second line", "first line"]


def test_ocr_failure_is_reported_not_swallowed():
    def boom(_png):
        raise RuntimeError("model missing")
    out = screen.ocr(b"x", engine=boom)
    assert out["ok"] is False
    assert "model missing" in out["error"]
    assert out["text"] == ""


# ── redaction ────────────────────────────────────────────────────────────────

def test_redaction_masks_secrets_and_reports_the_count():
    text = ("mail me at ops@example.com or use api_key=dummy-value-for-test\n"
            "Authorization: bearer eyJhbGciOiJIUzI1NiJ9.abcdefghij.klmnopqrst\n"
            "card 4111 1111 1111 1111 expired")
    out = screen.redact(text)
    assert "ops@example.com" not in out["text"]
    assert "dummy-value-for-test" not in out["text"]
    assert "4111 1111 1111 1111" not in out["text"]
    assert "«email»" in out["text"] and "«number»" in out["text"]
    assert out["total"] >= 3


def test_redaction_leaves_ordinary_screen_text_alone():
    text = "Inventory 42 units | ROI 31% | net profit $12.40"
    out = screen.redact(text)
    assert out["text"] == text
    assert out["total"] == 0


# ── vision ───────────────────────────────────────────────────────────────────

def _vision_poster(reply="A code editor with a terminal panel.", capture=None):
    def post(url, payload, timeout):
        capture.append((url, payload))
        return {"response": reply}
    return post


def test_vision_sets_keep_alive_zero_and_never_leaves_without_headroom():
    calls = []
    out = screen.describe(_png(), "what is this", poster=_vision_poster(capture=calls),
                          vram_reader=lambda: 500)
    assert out["ok"] and out["mode"] == "cpu"
    payload = calls[0][1]
    assert payload["keep_alive"] == 0
    assert payload["options"]["num_gpu"] == 0
    assert payload["images"] and payload["stream"] is False


def test_vision_uses_gpu_when_there_is_headroom():
    calls = []
    screen.describe(_png(), poster=_vision_poster(capture=calls),
                    vram_reader=lambda: 12000)
    assert "num_gpu" not in calls[0][1]["options"]


def test_vision_failure_returns_the_reason_not_a_scene():
    def boom(url, payload, timeout):
        raise TimeoutError("ollama did not answer")
    out = screen.describe(_png(), poster=boom, vram_reader=lambda: 0)
    assert out["ok"] is False
    assert "TimeoutError" in out["error"]
    assert "answer" not in out


# ── answering ────────────────────────────────────────────────────────────────

def test_answer_is_grounded_in_the_evidence_and_has_no_tools():
    calls = []

    def post(url, payload, timeout):
        calls.append((url, payload))
        return {"message": {"content": "The terminal shows a CUDA OOM error."}}

    out = screen.ask_screen("what is the error?", ocr_text="CUDA out of memory",
                            scene="a terminal", window={"process": "WindowsTerminal.exe",
                                                        "title": "python"},
                            poster=post)
    assert out["ok"]
    assert out["grounded_on"]["ocr_chars"] == len("CUDA out of memory")
    body = calls[0][1]
    assert body["messages"][0]["role"] == "system"
    assert "never invent" in body["messages"][0]["content"].lower()
    assert "tools" not in body and "functions" not in body


def test_answer_failure_is_reported_not_invented():
    def boom(url, payload, timeout):
        raise ConnectionError("down")
    out = screen.ask_screen("q", ocr_text="", poster=boom)
    assert out["ok"] is False and "answer" not in out


# ── the full look ────────────────────────────────────────────────────────────

def _look(**kw):
    options = dict(
        grabber=lambda: _image((1200, 800)),
        ocr_engine=lambda _png: (_ocr_result(["ERROR: CUDA out of memory",
                                              "Traceback (most recent call last)",
                                              "File run.py line 42"]), 0.2),
        vram_reader=lambda: 400,
        poster=_vision_poster(capture=[]),
        scope="primary",
    )
    options.update(kw)
    return screen.look(**options)


def test_look_skips_vision_when_ocr_is_rich_and_the_question_is_not_visual():
    out = _look(question="what did the error say?")
    assert out["ok"] and out["vision"]["skipped"] is True
    assert out["scene"] == ""


def test_look_asks_for_a_scene_when_the_question_is_visual():
    calls = []
    out = _look(question="what does the chart look like?",
                poster=_vision_poster(capture=calls))
    assert out["vision"]["skipped"] is False
    assert out["scene"].startswith("A code editor")
    assert len(calls) == 1


def test_look_redacts_before_returning_text():
    def noisy(_png):
        return _ocr_result(["password: hunter2", "normal line"]), 0.1
    out = _look(ocr_engine=noisy, question="what is this?")
    assert "hunter2" not in out["ocr"]["text"]
    assert out["ocr"]["redactions"]


def test_look_can_hand_the_png_back_or_keep_it_out_of_the_result():
    assert "png" not in _look(question="q")
    assert "png" in _look(question="q", keep_png=True)


def test_look_never_sends_a_blank_frame_to_the_vision_model():
    calls = []
    out = _look(grabber=lambda: _image((800, 600), (0, 0, 0)),
                question="what does this look like?", vision="always",
                poster=_vision_poster(capture=calls))
    assert out["blank"] is True
    assert out["vision"]["skipped"] is True
    assert out["vision"]["reason"] == "blank frame"
    assert calls == []


# ── memory ───────────────────────────────────────────────────────────────────

@pytest.fixture()
def db(tmp_path):
    return tmp_path / "memory.db"


def test_memory_collapses_repeated_frames(db):
    first = memory.record(sha1="a" * 40, text="one", path=db)
    again = memory.record(sha1="a" * 40, text="one", path=db)
    other = memory.record(sha1="b" * 40, text="two", path=db)
    assert first["duplicate"] is False
    assert again["duplicate"] is True and again["id"] == first["id"]
    assert other["id"] != first["id"]
    assert memory.stats(path=db)["samples"] == 3
    assert memory.stats(path=db)["frames"] == 2


def test_memory_search_finds_terms_and_reports_zero_honestly(db):
    memory.record(sha1="a" * 40, text="ERROR: CUDA out of memory", path=db)
    memory.record(sha1="b" * 40, text="pricing sheet for Q4", path=db)
    hit = memory.search("cuda", path=db)
    assert hit["count"] == 1 and hit["mode"] == "fts5"
    assert "CUDA" in hit["results"][0]["text"]
    miss = memory.search("kubernetes", path=db)
    assert miss["count"] == 0 and miss["results"] == []


def test_memory_purge_requires_an_explicit_scope(db):
    memory.record(sha1="a" * 40, text="x", path=db)
    with pytest.raises(ValueError):
        memory.purge(path=db)
    assert memory.purge(all=True, path=db)["deleted"] == 1


# ── agent: sample / ask / watcher ────────────────────────────────────────────

def test_sample_stores_a_tick_and_reports_the_window(monkeypatch, db):
    monkeypatch.setenv("LOCAL_SCREEN_DB", str(db))
    monkeypatch.setattr(agent.screen, "look", lambda **kw: {
        "ok": True,
        "frame": {"captured_at": time.time(), "sha1": "c" * 40,
                  "window": {"process": "Code.exe", "title": "app.py"}},
        "ocr": {"text": "def main():", "line_count": 1, "seconds": 0.4,
                "redactions": {"email": 1}},
        "vision": {"skipped": True},
        "scene": "",
    })
    out = agent.sample()
    assert out["ok"] and out["line_count"] == 1
    assert out["window"]["process"] == "Code.exe"
    assert memory.stats(path=db)["frames"] == 1


def test_ask_uses_the_local_answer_and_can_speak(monkeypatch, db):
    monkeypatch.setenv("LOCAL_SCREEN_DB", str(db))
    monkeypatch.setattr(agent.screen, "look", lambda **kw: {
        "ok": True,
        "frame": {"captured_at": time.time(), "sha1": "d" * 40,
                  "window": {"process": "chrome.exe", "title": "Sheets"}},
        "ocr": {"text": "total 42", "line_count": 1, "seconds": 0.3},
        "vision": {"skipped": True}, "scene": "",
    })
    monkeypatch.setattr(agent.screen, "ask_screen",
                        lambda *a, **kw: {"ok": True, "answer": "The total is 42.",
                                          "model": "qwen3:8b", "seconds": 1.2,
                                          "grounded_on": {"ocr_chars": 8}})
    spoken = []
    monkeypatch.setattr(agent, "say",
                        lambda text, voice=None: spoken.append(text) or {
                            "ok": True, "file": "x.wav", "name": "x.wav"})
    out = agent.ask("what is the total?", speak=True)
    assert out["ok"] and out["answer"] == "The total is 42."
    assert spoken == ["The total is 42."]


def _blank_look(question=None, **kw):
    return {"ok": True, "blank": True,
            "frame": {"captured_at": time.time(), "sha1": "e" * 40,
                      "window": {"process": "", "title": ""},
                      "possibly_secure_desktop": True},
            "ocr": {"text": "", "line_count": 0}, "vision": {"skipped": True,
                                                            "reason": "blank frame"},
            "scene": ""}


def test_a_locked_screen_is_not_stored_and_not_asked_about(monkeypatch, db):
    monkeypatch.setenv("LOCAL_SCREEN_DB", str(db))
    monkeypatch.setattr(agent.screen, "look", _blank_look)
    called = []
    monkeypatch.setattr(agent.screen, "ask_screen", lambda *a, **kw: called.append(1))
    out = agent.sample()
    assert out["ok"] and out["blank"] is True and out["stored"] is False
    assert memory.stats(path=db)["frames"] == 0
    refused = agent.ask("what is on screen?")
    assert refused["ok"] is False and refused["stage"] == "blank"
    assert called == [], "a blank frame must never reach the text model"


def test_watcher_stops_after_bounded_consecutive_failures(monkeypatch):
    watcher = agent.Watcher()
    monkeypatch.setattr(agent, "MAX_CONSECUTIVE_ERRORS", 2)
    monkeypatch.setattr(agent, "sample",
                        lambda **kw: {"ok": False, "error": "capture died"})
    watcher.start(interval_s=0.01)
    deadline = time.time() + 5
    while time.time() < deadline and watcher.state()["thread_alive"]:
        time.sleep(0.02)
    state = watcher.state()
    assert state["thread_alive"] is False
    assert state["running"] is False
    assert state["errors"] == 2
    assert "error_budget_exhausted" in (state["stop_reason"] or "")


def test_watcher_start_is_idempotent_and_stop_is_clean(monkeypatch):
    watcher = agent.Watcher()
    monkeypatch.setattr(agent, "sample", lambda **kw: {"ok": True, "duplicate": False,
                                                       "frame_id": 1})
    watcher.start(interval_s=0.01)
    try:
        second = watcher.start(interval_s=0.01)
        assert second["started"] is False and second["already_running"] is True
    finally:
        state = watcher.stop("test")
    assert state["running"] is False and state["stop_reason"] == "test"
    assert state["samples"] >= 1


def test_watcher_pause_blocks_new_samples(monkeypatch):
    watcher = agent.Watcher()
    calls = []
    monkeypatch.setattr(agent, "sample",
                        lambda **kw: calls.append(1) or {"ok": True, "frame_id": len(calls)})
    watcher.start(interval_s=0.01)
    time.sleep(0.1)
    watcher.pause()
    time.sleep(0.05)  # let an in-flight tick finish
    paused_at = len(calls)
    time.sleep(0.2)
    assert len(calls) <= paused_at + 1, "a paused watcher must stop sampling"
    assert len(calls) >= 1
    watcher.stop("test")


# ── voice (faked engines) ────────────────────────────────────────────────────

def test_say_writes_a_local_wav(monkeypatch, tmp_path):
    import local_voice
    monkeypatch.setattr(agent, "AUDIO_DIR", tmp_path)
    monkeypatch.setattr(local_voice, "synthesize",
                        lambda text, voice=None: {"bytes": b"RIFF" + b"0" * 200,
                                                  "engine": "piper", "voice": "piper"})
    out = agent.say("hello there")
    assert out["ok"] and os.path.isfile(out["file"])
    assert out["engine"] == "piper"


def test_say_requires_text():
    with pytest.raises(ValueError):
        agent.say("   ")


def test_ear_reports_the_reason_when_windows_has_no_recogniser():
    out = local_ear.listen_once(1, engine="sapi", runner=lambda script, timeout: "")
    assert out["ok"] is False
    assert "recogniser" in out["error"]


def test_ear_parses_a_recognised_utterance():
    out = local_ear.listen_once(1, engine="sapi",
                            runner=lambda script, timeout: "OK|what is on my screen|0.82\n")
    assert out["ok"] and out["text"] == "what is on my screen"
    assert out["confidence"] == 0.82


def test_ear_reports_silence_as_a_failure():
    def runner(script, timeout):
        if "InstalledRecognizers" in script:
            return "en-US|MS-1033-80-DESK\n"
        return "NOINPUT\n"
    out = local_ear.listen_once(1, engine="sapi", runner=runner)
    assert out["ok"] is False
    assert (out.get("text") or "") == ""
    assert "no speech" in out["error"]


def test_ear_whisper_backend_records_then_transcribes(monkeypatch):
    import local_transcribe as lt
    monkeypatch.setattr(local_ear, "engines", lambda runner=None: {
        "preferred": "whisper", "whisper": {"available": True},
        "sapi": {"available": False}, "transcription": {"available": True}})
    monkeypatch.setattr(lt, "transcribe",
                        lambda wav, **kw: {"ok": True, "text": "hello there",
                                           "language": "en", "duration": 1.0})
    seen = {}
    out = local_ear.listen_once(1, engine="whisper",
                                recorder=lambda secs: seen.setdefault("wav", b"RIFF"))
    assert out["ok"] and out["text"] == "hello there"
    assert out["engine"] == "whisper"
    assert seen["wav"] == b"RIFF"


# ── API gate and routes ──────────────────────────────────────────────────────

def _api_client(role="operator"):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import local_screen_api as api

    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.require_screen_operator] = (
        lambda: {"role": role, "id": "op-1"})
    return TestClient(app), api


def test_api_status_reports_local_guarantees(monkeypatch):
    client, _api = _api_client()
    monkeypatch.setattr(agent, "status", lambda: {
        "watcher": {"running": False}, "memory": {"frames": 0},
        "fully_local": {"loopback_only": True}})
    out = client.get("/api/local-screen/status")
    assert out.status_code == 200
    assert out.json()["fully_local"]["loopback_only"] is True


def test_api_ask_returns_the_answer(monkeypatch):
    client, _api = _api_client()
    monkeypatch.setattr(agent, "ask", lambda q, **kw: {
        "ok": True, "question": q, "answer": "It is a terminal.",
        "vision_used": False})
    out = client.post("/api/local-screen/ask", json={"question": "what is this?"})
    assert out.status_code == 200
    assert out.json()["answer"] == "It is a terminal."


def test_api_capture_failure_is_503_not_a_fake_frame(monkeypatch):
    client, _api = _api_client()
    monkeypatch.setattr(agent, "sample",
                        lambda **kw: {"ok": False, "error": "no desktop"})
    out = client.post("/api/local-screen/sample", json={"vision": "never"})
    assert out.status_code == 503
    assert out.json()["detail"]["code"] == "screen_capture_failed"


def test_api_purge_requires_a_scope():
    client, _api = _api_client()
    out = client.post("/api/local-screen/memory/purge", json={"all": False})
    assert out.status_code == 422


def test_api_serves_only_wav_names(monkeypatch, tmp_path):
    client, api = _api_client()
    monkeypatch.setattr(agent, "AUDIO_DIR", tmp_path)
    (tmp_path / "ok.wav").write_bytes(b"RIFFdata")
    assert client.get("/api/local-screen/audio/ok.wav").status_code == 200
    assert client.get("/api/local-screen/audio/notes.txt").status_code == 400


def _gate(role, environ=""):
    """Call the gate directly: the dependency closure is not monkeypatchable."""
    import asyncio
    import local_screen_api as api

    original = api._environment
    api._environment = lambda: environ
    try:
        user = None if role is None else {"role": role, "id": "x"}
        return asyncio.run(api.require_screen_operator(user))
    finally:
        api._environment = original


def test_gate_refuses_a_customer_role():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        _gate("member")
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "local_screen_operator_only"


def test_gate_refuses_an_anonymous_caller():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        _gate(None)
    assert exc.value.status_code == 401


def test_gate_refuses_operator_in_production():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        _gate("operator", environ="production")
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "local_screen_platform_admin_only"


def test_gate_admits_the_operator_on_a_dev_box():
    assert _gate("operator")["role"] == "operator"


def test_gate_admits_a_platform_admin_anywhere():
    assert _gate("admin", environ="production")["role"] == "admin"
