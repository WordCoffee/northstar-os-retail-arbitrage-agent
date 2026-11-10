"""Tests for the Bojo publishing tools (`compose_listing`, `build_dieline`).

Offline: no model, no network, no database. ``compose_listing`` is driven
through a fake provider, so the REAL ``reasoning_tasks.listing_proposal``
normalisation runs (length limits, prohibited words, copy audit) against a
canned model response. ``build_dieline`` runs the real print engine and the
real geometry gate for the pass path, and a fake printer/auditor prove the
injection seam.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from adapters.base import ProviderResponse, ProviderStatus  # noqa: E402
from bojo_tools import publishing  # noqa: E402
from bojo_tools.publishing import (  # noqa: E402
    TOOLS,
    build_dieline,
    compose_listing,
)


# ---------------------------------------------------------------------------
# Fakes.
# ---------------------------------------------------------------------------


class FakeProvider:
    """A reasoning provider that returns whatever it is constructed with."""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.response


def _response(proposed, warnings=None):
    content = json.dumps({
        "sku": "SKU-1",
        "original": {"title": "Old title", "bullets": [], "description": ""},
        "proposed": proposed,
        "reasons": ["led with the head term"],
        "missing_evidence": ["unit weight"],
        "warnings": warnings or [],
    })
    return ProviderResponse(
        success=True, status=ProviderStatus.OK, provider="fake",
        data={"content": content, "model": "fake-model"}, latency_ms=1.0,
    )


class FakePrinter:
    def __init__(self, build=None, error=None, svg="<svg id='fake'></svg>"):
        self.build = build
        self.error = error
        self.svg = svg
        self.calls = []

    def build_from_template(self, template_id, params):
        self.calls.append({"template_id": template_id, "params": params})
        if self.error is not None:
            raise self.error
        return self.build

    def render_svg(self, build):
        return self.svg

    def render_pdf(self, build):
        return b"%PDF-1.4 fake"


class FakeGeometry:
    def __init__(self, audit=None, error=None):
        self._audit = audit or {"ok": True, "violations": []}
        self.error = error

    def audit(self, build):
        if self.error is not None:
            raise self.error
        return self._audit


BUILD = {
    "title": "Stand-up pouch",
    "width_mm": 138.0,
    "height_mm": 466.0,
    "meta": {"kind": "doypack", "bleed_mm": 3.0, "safe_mm": 5.0},
    "layers": [
        {"layer": "bleed", "kind": "rect"},
        {"layer": "trim", "kind": "rect"},
        {"layer": "fold", "kind": "line"},
        {"layer": "safe", "kind": "rect"},
    ],
}


# ---------------------------------------------------------------------------
# Registry.
# ---------------------------------------------------------------------------


def test_tools_registry_exports_both_publishing_tools():
    assert set(TOOLS) == {"compose_listing", "build_dieline"}
    assert TOOLS["compose_listing"] is compose_listing
    assert TOOLS["build_dieline"] is build_dieline


# ---------------------------------------------------------------------------
# compose_listing.
# ---------------------------------------------------------------------------


def test_compose_listing_returns_a_proposal_from_an_injected_provider():
    provider = FakeProvider(_response({
        "title": "Northstar Organic Matcha 30 Servings",
        "bullets": ["GRADE A: stone milled", "30 SERVINGS: one tin"],
        "description": "Northstar matcha, stone milled.",
        "attributes": {"brand": "Northstar"},
    }))

    result = compose_listing(
        sku="SKU-1",
        title="matcha",
        bullets=["stone milled"],
        description="matcha powder",
        keywords=["matcha", "green tea"],
        brand="Northstar",
        provider=provider,
    )

    assert result["ok"] is True
    assert result["tool"] == "compose_listing"
    data = result["data"]
    assert data["sku"] == "SKU-1"
    assert data["proposed"]["title"] == "Northstar Organic Matcha 30 Servings"
    assert data["reasons"] == ["led with the head term"]
    assert data["missing_evidence"] == ["unit weight"]
    assert data["applied"] is False
    # The real normalisation ran: provenance came from the provider payload.
    assert data["provenance"]["model"] == "fake-model"
    assert "copy_audit" in data
    # The production function received the real request shape.
    assert len(provider.requests) == 1
    assert provider.requests[0].task_type == "listing"
    assert provider.requests[0].session_id == "listing:SKU-1"
    json.dumps(result)  # contract: JSON-serialisable


def test_compose_listing_flags_prohibited_words_through_the_real_validator():
    provider = FakeProvider(_response({
        "title": "Best Matcha 100% Guaranteed",
        "bullets": ["AMAZING: free shipping"],
        "description": "The best matcha you can buy.",
        "attributes": {},
    }))

    result = compose_listing(sku="SKU-2", title="matcha", provider=provider)

    assert result["ok"] is True
    warnings = " ".join(result["data"]["warnings"]).lower()
    assert "prohibited phrase" in warnings


def test_compose_listing_provider_failure_is_a_business_failure():
    provider = FakeProvider(ProviderResponse(
        success=False, status=ProviderStatus.ERROR, provider="fake",
        error="provider down",
    ))

    result = compose_listing(sku="SKU-3", title="matcha", provider=provider)

    assert result["ok"] is False
    assert result["tool"] == "compose_listing"
    assert result["reason"].startswith("listing composer refused:")
    assert "provider down" in result["reason"]


def test_compose_listing_empty_copy_is_a_business_failure():
    result = compose_listing(sku="SKU-4", title="   ")

    assert result == {
        "ok": False,
        "tool": "compose_listing",
        "reason": "at least one of title, bullets or description is required",
    }


def test_compose_listing_composer_that_raises_is_reported_not_raised():
    class Broken:
        def listing_proposal(self, **kwargs):
            raise RuntimeError("prompt builder exploded")

    result = compose_listing(sku="SKU-5", title="matcha", composer=Broken())

    assert result["ok"] is False
    assert result["reason"].startswith("listing composer failed: RuntimeError")


def test_compose_listing_programmer_errors_raise():
    with pytest.raises(TypeError):
        compose_listing(sku=5)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        compose_listing(sku="SKU-6", bullets=[1])  # type: ignore[list-item]
    with pytest.raises(TypeError):
        compose_listing(sku="SKU-6", attributes=["brand"])  # type: ignore[arg-type]


def test_default_composer_is_the_real_reasoning_tasks_module():
    import reasoning_tasks

    assert publishing._default_composer() is reasoning_tasks
    assert compose_listing.__defaults__[-1] is None  # composer defaults to None


# ---------------------------------------------------------------------------
# build_dieline.
# ---------------------------------------------------------------------------


def test_build_dieline_runs_the_real_engine_and_geometry_gate():
    result = build_dieline("doypack", {"width_mm": 120, "height_mm": 200})

    assert result["ok"] is True
    assert result["tool"] == "build_dieline"
    data = result["data"]
    assert data["template_id"] == "doypack"
    assert data["width_mm"] > 0 and data["height_mm"] > 0
    assert data["audit"]["ok"] is True
    assert set(data["layers"]) >= {"bleed", "trim", "fold", "safe"}
    assert data["svg_bytes"] > 0
    assert data["formats"] == ["svg"]
    assert "svg" not in data  # not returned unless asked for
    json.dumps(result)


def test_build_dieline_can_return_the_svg_markup_and_a_pdf():
    result = build_dieline("label_rectangle", include_svg=True, pdf=True)

    assert result["ok"] is True
    assert result["data"]["svg"].startswith("<svg")
    assert result["data"]["formats"] == ["svg", "pdf"]
    assert result["data"]["pdf_bytes"] > 0


def test_build_dieline_with_injected_printer_and_auditor():
    printer = FakePrinter(build=dict(BUILD))
    geometry = FakeGeometry()

    result = build_dieline("doypack", {"width_mm": 120}, printer=printer, geometry=geometry)

    assert result["ok"] is True
    assert result["data"]["elements"] == 4
    assert result["data"]["layers"] == ["bleed", "trim", "fold", "safe"]
    assert result["data"]["svg_bytes"] == len("<svg id='fake'></svg>")
    assert printer.calls == [{"template_id": "doypack", "params": {"width_mm": 120}}]


def test_build_dieline_unknown_template_is_a_business_failure():
    result = build_dieline("no_such_template")

    assert result["ok"] is False
    assert result["tool"] == "build_dieline"
    assert result["reason"].startswith("dieline rejected:")
    assert "unknown template_id" in result["reason"]


def test_build_dieline_rejected_geometry_is_a_business_failure():
    printer = FakePrinter(error=ValueError("safe margin inverts on the face"))
    result = build_dieline("label_square", printer=printer)

    assert result["ok"] is False
    assert "safe margin inverts" in result["reason"]


def test_build_dieline_engine_failure_is_reported_not_raised():
    printer = FakePrinter(error=RuntimeError("renderer exploded"))
    result = build_dieline("doypack", printer=printer)

    assert result["ok"] is False
    assert result["reason"].startswith("dieline build failed: RuntimeError")


def test_build_dieline_programmer_errors_raise():
    with pytest.raises(TypeError):
        build_dieline(5)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        build_dieline("doypack", params=["width"])  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        build_dieline("doypack", include_svg="yes")  # type: ignore[arg-type]
