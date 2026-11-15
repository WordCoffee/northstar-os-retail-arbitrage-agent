"""Ty's capability toolkit: capture→client, open media, hardening, UI specs, proposals, mesh routing.

Every module is a pure core plus a small CLI. Network and install steps are injected seams so the
test suite is offline and a refused step is a named result, never a silent no-op.

Submodules are imported on demand (``from tools.ty_toolkit import capture``), so a module that is
not needed costs nothing and ``python -m`` does not import it twice.
"""

__all__ = ["capture", "openverse", "hardening", "ui_benchmark", "proposals", "mesh_route"]
