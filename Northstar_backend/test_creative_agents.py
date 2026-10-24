"""Tests for the four creative specialists + the GPU job queue.

Every rule cited here was verified during the Phase 1 study (research/).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specialists import content, image_aplus, job_queue, social_graphics, video_ugc  # noqa: E402


# ── A+ ─────────────────────────────────────────────────────────────────────

def test_aplus_plans_the_default_story_with_exact_sizes():
    out = image_aplus.plan(spec={"product": "Lion's Mane powder"})
    assert out["ok"] is True
    sizes = {m["module"]: m.get("size") for m in out["modules"]}
    assert sizes["header"] == "970x600"
    assert sizes["banner"] == "970x300"
    assert sizes["three_tiles"] == "300x300"
    assert sizes["four_tiles"] == "220x220"
    assert "comparison" in sizes


def test_aplus_flags_prohibited_copy():
    out = image_aplus.plan(spec={"product": "x",
                                 "copy": "On sale now, $19.99, better than Brand Y"})
    kinds = {h["kind"] for h in out["copy_check"]}
    assert {"price", "promotion", "competitor"} <= kinds


def test_aplus_module_image_validation_checks_size_and_bytes(tmp_path):
    p = tmp_path / "header.png"
    Image.new("RGB", (970, 600), (255, 255, 255)).save(p)
    assert image_aplus.validate_module_image(p, "header")["ok"] is True

    bad = tmp_path / "bad.png"
    Image.new("RGB", (300, 300), (255, 255, 255)).save(bad)
    out = image_aplus.validate_module_image(bad, "header")
    assert out["ok"] is False and "does not match" in out["problems"][0]


def test_aplus_asks_for_the_product():
    out = image_aplus.plan(spec={})
    assert out["ok"] is False and out["status"] == "needs_input"


# ── social ─────────────────────────────────────────────────────────────────

def test_social_plans_each_requested_aspect_with_sizes():
    out = social_graphics.plan(spec={"product": "pouch", "content_type": "ad",
                                     "aspects": ["1:1", "9:16"]})
    assert out["ok"] is True
    sizes = [l["size"] for l in out["layouts"]]
    assert sizes == ["1080x1080", "1080x1920"]
    assert "top 14%" in out["layouts"][1]["safe_zone"]


def test_social_asks_for_the_content_type():
    out = social_graphics.plan(spec={"product": "pouch"})
    assert out["ok"] is False and out["questions"][0]["field"] == "content_type"


# ── video ──────────────────────────────────────────────────────────────────

def test_video_5s_storyboard_is_exactly_five_seconds():
    out = video_ugc.plan(spec={"product": "pouch", "duration_seconds": 5})
    assert out["ok"] is True
    total = sum(s["seconds"] for s in out["scenes"])
    assert abs(total - 5.0) < 1e-6
    assert out["frames"] == 120  # 5 s * 24 fps


def test_video_rejects_an_unsupported_duration():
    out = video_ugc.plan(spec={"product": "pouch", "duration_seconds": 7})
    assert out["ok"] is False and out["status"] == "rejected"


def test_duration_is_verified_from_frames_not_a_badge():
    ok = video_ugc.validate_duration(frame_count=120, fps=24, expected_seconds=5)
    assert ok["ok"] is True and ok["measured_seconds"] == 5.0
    bad = video_ugc.validate_duration(frame_count=240, fps=24, expected_seconds=5)
    assert bad["ok"] is False and "expected 5s" in bad["problems"][0]


def test_video_flags_medical_claims_in_the_script():
    out = video_ugc.plan(spec={"product": "pouch", "duration_seconds": 5,
                               "script": "This cures fatigue."})
    assert out["claims_check"] and out["claims_check"][0]["match"].lower() == "cures"


# ── content ────────────────────────────────────────────────────────────────

def test_content_writes_three_variants_with_coverage():
    out = content.plan(spec={"product": "Lion's Mane Powder", "surface": "ad",
                             "keywords": ["lion's mane", "mushroom powder"]})
    assert out["ok"] is True and len(out["variants"]) == 3
    assert all("coverage" in v for v in out["variants"])


def test_content_flags_disease_claims_and_does_not_mark_them_safe():
    out = content.plan(spec={"product": "Lion's Mane", "surface": "ad",
                             "benefits": ["cures arthritis"]})
    assert any(not v["safe"] for v in out["variants"])


def test_content_rejects_an_unknown_surface():
    out = content.plan(spec={"product": "x", "surface": "billboard"})
    assert out["ok"] is False and out["status"] == "rejected"


# ── job queue ──────────────────────────────────────────────────────────────

def test_queue_runs_one_heavy_job_at_a_time():
    q = job_queue.JobQueue()
    q.submit("image", {"n": 1})
    got = q.acquire()
    assert got["ok"] is True
    second = q.acquire()
    assert second["ok"] is False and second["reason"] == "busy"


def test_interactive_jumps_ahead_of_batch():
    q = job_queue.JobQueue()
    q.submit("video", priority="batch")
    q.submit("image", priority="interactive")
    got = q.acquire()
    assert got["job"]["kind"] == "image"


def test_the_vram_guard_blocks_a_job_and_says_why():
    q = job_queue.JobQueue(vram_guard=lambda: False)
    q.submit("video")
    got = q.acquire()
    assert got["ok"] is False and got["reason"] == "vram_guard"
    assert q.status()["running"] is None


def test_completion_records_cost_and_writes_the_ledger(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    q = job_queue.JobQueue(ledger_path=ledger)
    job = q.submit("image")
    q.acquire()
    q.complete(job["job_id"], ok=True, credits=34, cost_usd=0.0, outputs=["a.png"])
    assert ledger.is_file() and "a.png" in ledger.read_text(encoding="utf-8")
    totals = q.totals()
    assert totals["jobs"] == 1 and totals["credits"] == 34


def test_completing_an_unknown_job_is_refused():
    q = job_queue.JobQueue()
    assert q.complete("nope", ok=True)["ok"] is False
