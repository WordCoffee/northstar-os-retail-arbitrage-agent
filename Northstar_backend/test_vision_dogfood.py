"""V9 dogfood harness: the seller task is checkable, and a locked desktop is a refusal."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from vision import dogfood  # noqa: E402


def test_the_seller_task_passes_a_real_page():
    text = ("Competitor Monitor — price changes. Competitor A dropped its price by 12%. "
            "Save this change or refresh the board.")
    result = dogfood.seller_task("competitor-monitor", text)
    assert result["ok"] is True
    assert "competitor" in result["vocabulary"]
    assert result["has_number"] is True


def test_the_seller_task_fails_an_empty_shell():
    result = dogfood.seller_task("listings", "Loading…")
    assert result["ok"] is False
    assert "did not show" in result["why"]


def test_the_seller_task_needs_a_number_not_just_vocabulary():
    result = dogfood.seller_task("socialpulse", "Social posts reach an audience")
    assert result["ok"] is False
    assert result["has_number"] is False


def test_a_run_without_a_live_session_records_the_refusal(tmp_path):
    payload = dogfood.run(services=["listings"], out=tmp_path / "d.json")
    assert payload["pass"] is False
    row = payload["services"][0]
    assert row["blocked"] is True
    assert "unlocked" in row["reason"]
    assert json.loads((tmp_path / "d.json").read_text(encoding="utf-8"))["passed"] == 0


def test_a_live_run_is_scored_per_service(tmp_path, monkeypatch):
    monkeypatch.setattr(dogfood, "SHOTS", tmp_path / "shots")
    pages = {
        "http://x/competitor-monitor": ("Competitor Monitor", "Competitor price 12%"),
        "http://x/listings": ("Listings", "Listing title price 19.99"),
        "http://x/socialpulse": ("SocialPulse", "Social post reach"),
    }

    def open_url(url):
        title, _ = pages[url]
        return {"ok": True, "title": title}

    counter = {"i": 0}
    order = list(pages.values())

    def read_text():
        text = order[counter["i"]][1]
        counter["i"] += 1
        return {"ok": True, "text": text}

    payload = dogfood.run(services=["competitor-monitor", "listings", "socialpulse"],
                          open_url=open_url, read_text=read_text,
                          shot=lambda: {"png": b"png"}, base="http://x",
                          out=tmp_path / "d.json")
    assert payload["total"] == 3
    assert payload["passed"] == 3 and payload["pass"] is True
    assert payload["services"][0]["screenshot"].endswith(".png")
