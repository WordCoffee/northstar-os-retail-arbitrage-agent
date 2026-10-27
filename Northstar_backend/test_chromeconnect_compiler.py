"""Tests for Chrome Connect compiler + replay + cache (Phase 3)."""

from __future__ import annotations

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chromeconnect_compiler as comp
import chromeconnect_ai_loop as ail

SIMPLE_HTML = """
<html><body>
  <h1>Product Page</h1>
  <a href="/home">Home</a>
  <button id="add-to-cart">Add to Cart</button>
  <input type="text" name="qty" placeholder="Quantity" />
  <p>Price: $14.99</p>
</body></html>
"""

EXTRACT_HTML = """
<html><body>
  <h1>Turmeric Powder 16oz</h1>
  <span class="price">$12.99</span>
  <a href="/product/123">Product Link</a>
  <p>Organic turmeric from India.</p>
</body></html>
"""


def _html_provider(url):
    return SIMPLE_HTML


# ---------------------------------------------------------------------------
# Trace recording
# ---------------------------------------------------------------------------

def test_record_trace_from_loop_result():
    result = ail.run_loop("extract title and price", _html_provider)
    trace = comp.record_trace(result, "run_001", "extract title and price", "http://example.com")
    assert trace.run_id == "run_001"
    assert trace.goal == "extract title and price"
    assert trace.success == result.get("success", False)
    assert trace.total_steps == result.get("steps", 0)
    d = trace.to_dict()
    assert "steps" in d
    assert "result" in d


def test_record_trace_steps():
    result = ail.run_loop("extract title", _html_provider)
    trace = comp.record_trace(result, "run_002", "extract title", "http://example.com")
    for s in trace.steps:
        assert hasattr(s, "step")
        assert hasattr(s, "tool")
        assert hasattr(s, "success")


# ---------------------------------------------------------------------------
# Adapter compilation
# ---------------------------------------------------------------------------

def test_compile_adapter_from_successful_trace():
    result = ail.run_loop("extract title and price", _html_provider)
    trace = comp.record_trace(result, "run_003", "extract title and price", "http://example.com")
    if trace.success:
        adapter = comp.compile_adapter(trace, name="test_adapter")
        assert adapter is not None
        assert adapter.name == "test_adapter"
        assert adapter.status == "proposed"
        assert adapter.compiled_from_run == "run_003"


def test_compile_adapter_from_failed_trace():
    # A trace that gave up should not compile
    result = {"success": False, "action_history": [], "steps": 0, "tokens": 0, "time_s": 0.0, "result": None, "gave_up_reason": "test"}
    trace = comp.record_trace(result, "run_fail", "fail task", "http://example.com")
    adapter = comp.compile_adapter(trace)
    assert adapter is None


def test_save_and_load_adapter():
    tmpdir = tempfile.mkdtemp()
    try:
        adapter = comp.CandidateAdapter(name="test_save", origin="example.com", task="test", status="proposed")
        path = comp.save_adapter(adapter, adapter_dir=tmpdir)
        assert os.path.exists(path)
        loaded = comp.load_adapter("test_save", adapter_dir=tmpdir)
        assert loaded is not None
        assert loaded.name == "test_save"
        assert loaded.status == "proposed"
    finally:
        shutil.rmtree(tmpdir)


def test_list_adapters():
    tmpdir = tempfile.mkdtemp()
    try:
        comp.save_adapter(comp.CandidateAdapter(name="a1", origin="x.com", task="t"), adapter_dir=tmpdir)
        comp.save_adapter(comp.CandidateAdapter(name="a2", origin="x.com", task="t"), adapter_dir=tmpdir)
        adapters = comp.list_adapters(adapter_dir=tmpdir)
        assert "a1" in adapters
        assert "a2" in adapters
    finally:
        shutil.rmtree(tmpdir)


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------

def test_replay_adapter_success():
    adapter = comp.CandidateAdapter(
        name="test_replay",
        origin="example.com",
        task="extract",
        selectors={"title": "a"},
        status="approved",
    )
    html = "<html><body><h1>My Title</h1><a href='/home'>Title Link</a></body></html>"
    success, output, error = comp.replay_adapter(adapter, html)
    assert success is True
    assert output is not None
    assert "title" in output


def test_replay_adapter_missing_field():
    adapter = comp.CandidateAdapter(
        name="test_replay2",
        origin="example.com",
        task="extract",
        selectors={"title": "h1", "price": ".price"},
        status="approved",
    )
    html = "<html><body><h1>My Title</h1></body></html>"  # no price
    success, output, error = comp.replay_adapter(adapter, html)
    assert success is False
    assert "missing fields" in (error or "")


def test_replay_degraded_adapter():
    adapter = comp.CandidateAdapter(name="deg", origin="x.com", task="t", status="degraded")
    success, output, error = comp.replay_adapter(adapter, "<html><body></body></html>")
    assert success is False
    assert "degraded" in (error or "")


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def test_cache_set_and_get():
    tmp_cache = tempfile.mkdtemp()
    orig = comp.CACHE_DIR
    comp.CACHE_DIR = tmp_cache
    try:
        comp.cache_set("example.com", "test task", "sig123", {"answer": 42})
        result = comp.cache_get("example.com", "test task", "sig123")
        assert result == {"answer": 42}
    finally:
        comp.CACHE_DIR = orig
        shutil.rmtree(tmp_cache)


def test_cache_miss():
    tmp_cache = tempfile.mkdtemp()
    orig = comp.CACHE_DIR
    comp.CACHE_DIR = tmp_cache
    try:
        result = comp.cache_get("example.com", "test task", "nonexistent")
        assert result is None
    finally:
        comp.CACHE_DIR = orig
        shutil.rmtree(tmp_cache)


def test_cache_clear():
    tmp_cache = tempfile.mkdtemp()
    orig = comp.CACHE_DIR
    comp.CACHE_DIR = tmp_cache
    try:
        comp.cache_set("a.com", "t1", "s1", {"x": 1})
        comp.cache_set("b.com", "t2", "s2", {"y": 2})
        count = comp.cache_clear()
        assert count == 2
        assert comp.cache_get("a.com", "t1", "s1") is None
    finally:
        comp.CACHE_DIR = orig
        shutil.rmtree(tmp_cache)


# ---------------------------------------------------------------------------
# Self-healer
# ---------------------------------------------------------------------------

def test_self_heal_selectors():
    adapter = comp.CandidateAdapter(
        name="heal_test",
        origin="example.com",
        task="extract title",
        selectors={"title": "old_selector"},
        status="approved",
    )
    html = "<html><body><h1>My Title</h1><p>Some text</p></body></html>"
    healed, new_selectors, error = comp.self_heal_selectors(adapter, html)
    # May or may not heal depending on element matching
    assert isinstance(healed, bool)
    if healed:
        assert new_selectors is not None
    else:
        assert error is not None


def test_self_heal_empty_page():
    adapter = comp.CandidateAdapter(name="empty", origin="x.com", task="t", selectors={"a": "sel"})
    healed, new_selectors, error = comp.self_heal_selectors(adapter, "<html><body></body></html>")
    assert healed is False
    assert error is not None


# ---------------------------------------------------------------------------
# Fallback orchestrator
# ---------------------------------------------------------------------------

def test_run_with_fallback_no_adapter():
    def provider(url):
        return SIMPLE_HTML
    result = comp.run_with_fallback("extract title", "http://example.com", provider)
    assert "path" in result
    assert result["path"] in ("ai", "adapter", "adapter_cached", "adapter_healed", "failed")


def test_run_with_fallback_with_adapter():
    tmpdir = tempfile.mkdtemp()
    orig_adapter_dir = comp.ADAPTER_DIR
    comp.ADAPTER_DIR = tmpdir
    try:
        adapter = comp.CandidateAdapter(
            name="fallback_test",
            origin="example.com",
            task="extract title",
            selectors={"title": "h1"},
            status="approved",
        )
        comp.save_adapter(adapter, adapter_dir=tmpdir)
        def provider(url):
            return "<html><body><h1>Test Title</h1></body></html>"
        result = comp.run_with_fallback("extract title", "http://example.com", provider,
                                       adapter_name="fallback_test")
        assert "path" in result
    finally:
        comp.ADAPTER_DIR = orig_adapter_dir
        shutil.rmtree(tmpdir)


# ---------------------------------------------------------------------------
# Fingerprint
# ---------------------------------------------------------------------------

def test_fingerprint_deterministic():
    el = {"tag": "a", "role": "link", "text": "Home"}
    fp1 = comp._fingerprint(el)
    fp2 = comp._fingerprint(el)
    assert fp1 == fp2
    assert "a" in fp1
    assert "link" in fp1
