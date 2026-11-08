"""The `measured` dimension is a real check, and a missing artefact is a named zero."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import measured  # noqa: E402


def test_routes_are_parsed_from_jsx():
    text = ('<Route path="/home" element={<CommandCenter />} />\n'
            '<Route path="/listings" element={<ListingGuardian />} />')
    found = measured.routes(text)
    assert {"path": "/home", "component": "CommandCenter"} in found
    assert {"path": "/listings", "component": "ListingGuardian"} in found


def test_nav_routes_come_from_the_shell_registry(tmp_path, monkeypatch):
    src = tmp_path / "src"
    (src / "data").mkdir(parents=True)
    (src / "data" / "services.js").write_text(
        "{ id: 'prospector', route: '/prospector' },\n"
        '{ id: "thewatch", route: "/thewatch" },\n', encoding="utf-8")
    monkeypatch.setattr(measured, "SRC", src)
    assert set(measured.nav_routes()) == {"/prospector", "/thewatch"}


def test_component_files_map_exports_to_paths(tmp_path, monkeypatch):
    src = tmp_path / "src"
    (src / "pages").mkdir(parents=True)
    (src / "pages" / "Prospector.jsx").write_text(
        "export default function Prospector() { return null }\n", encoding="utf-8")
    monkeypatch.setattr(measured, "SRC", src)
    table = measured.component_files()
    assert "Prospector" in table
    assert table["Prospector"].endswith("Prospector.jsx")


def test_measure_wires_a_lazy_import_and_scores_it(tmp_path, monkeypatch):
    src = tmp_path / "src"
    (src / "pages" / "customer").mkdir(parents=True)
    (src / "pages" / "customer" / "AccountStatus.jsx").write_text(
        "export default function AccountStatus() { return null }\n", encoding="utf-8")
    app = src / "App.jsx"
    app.write_text(
        "const CustomerAccount = lazy(() => import('./pages/customer/AccountStatus.jsx'))\n"
        '<Route path="/account" element={<CustomerAccount />} />\n', encoding="utf-8")
    registry = tmp_path / "services.json"
    registry.write_text(json.dumps({"services": [
        {"id": "account", "route": "/account"}]}), encoding="utf-8")

    monkeypatch.setattr(measured, "SRC", src)
    monkeypatch.setattr(measured, "APP_JSX", app)
    monkeypatch.setattr(measured, "REGISTRY", registry)
    monkeypatch.setattr(measured, "api_latency", lambda: {"ok": True, "p95_ms": 5.0})

    result = measured.measure(out=tmp_path / "measured.json")
    row = result["services"]["account"]
    assert row["pass"] is True
    assert row["score"] == 100.0
    assert "AccountStatus.jsx" in row["evidence"]


def test_an_unregistered_route_is_a_named_zero(tmp_path, monkeypatch):
    src = tmp_path / "src"
    src.mkdir(parents=True)
    app = src / "App.jsx"
    app.write_text("<div />", encoding="utf-8")
    registry = tmp_path / "services.json"
    registry.write_text(json.dumps({"services": [
        {"id": "ghost", "route": "/ghost"}]}), encoding="utf-8")
    monkeypatch.setattr(measured, "SRC", src)
    monkeypatch.setattr(measured, "APP_JSX", app)
    monkeypatch.setattr(measured, "REGISTRY", registry)
    monkeypatch.setattr(measured, "api_latency", lambda: {"ok": True, "p95_ms": 5.0})

    result = measured.measure(out=tmp_path / "measured.json")
    row = result["services"]["ghost"]
    assert row["pass"] is False and row["score"] == 0.0
    assert "not registered" in row["evidence"]


def test_a_slow_app_fails_every_service(tmp_path, monkeypatch):
    src = tmp_path / "src"
    (src / "pages").mkdir(parents=True)
    (src / "pages" / "Hub.jsx").write_text(
        "export default function Hub() { return null }\n", encoding="utf-8")
    app = src / "App.jsx"
    app.write_text('<Route path="/hub" element={<Hub />} />', encoding="utf-8")
    registry = tmp_path / "services.json"
    registry.write_text(json.dumps({"services": [{"id": "hub", "route": "/hub"}]}),
                        encoding="utf-8")
    monkeypatch.setattr(measured, "SRC", src)
    monkeypatch.setattr(measured, "APP_JSX", app)
    monkeypatch.setattr(measured, "REGISTRY", registry)
    monkeypatch.setattr(measured, "api_latency",
                        lambda: {"ok": False, "reason": "timeout", "p95_ms": 5000})

    result = measured.measure(out=tmp_path / "measured.json")
    assert result["services"]["hub"]["score"] == 0.0
    assert "latency" in result["services"]["hub"]["evidence"]


def test_score_for_without_an_artefact_is_zero_with_a_reason(tmp_path):
    verdict = measured.score_for("prospector", {"services": {}})
    assert verdict["score"] == 0.0
    assert "no measurement artefact" in verdict["evidence"]


def test_the_live_artefact_covers_every_service():
    """The real run must cover the registry; a partial artefact would silently zero scores."""
    data = measured.load()
    if not data:
        return  # no artefact in this checkout: the zero is honest and the test is moot
    registry = json.loads((ROOT / "ty" / "services.json").read_text(encoding="utf-8"))
    ids = {row["id"] for row in registry.get("services") or []}
    assert ids <= set((data.get("services") or {}))
