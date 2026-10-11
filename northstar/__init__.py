"""NorthstarOS control layer (secure control-layer build).

New, security-first packages live here, separate from the legacy app:

- ``northstar.security`` — Phase 1: redaction, secret scanning.
- ``northstar.policy``   — Phase 2: deterministic policy kernel (planned).
- ``northstar.gateway``  — Phase 3: Lightpanda Connect gateway (planned).
- ``northstar.brain``    — Phase 5: Master Brain Kernel (planned).

Conventions: stdlib-only unless explicitly reviewed; no I/O at import time;
no secrets read from files; deterministic and unit-testable.
"""
