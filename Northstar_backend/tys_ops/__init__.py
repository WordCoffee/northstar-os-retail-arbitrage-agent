"""Tys Assistant operations layer.

The agent itself lives in :mod:`tys_assistant` (queue, lanes, evidence). This
package holds the infrastructure around it, each module independent and
testable on its own:

===================  ==========================================================
``storage``          hybrid local-master storage: tiers, quotas, pruning,
                     retention, download prompts, purge.
``bridge``           cloud sync bridge: signed tokens, offline queue, sync
                     envelopes, gateway/DNS descriptor.
``validators``       structural + semantic validation suite, including hunk
                     arithmetic and workspace-derived acceptance.
``memory``           long-term context index, compression, vector retrieval,
                     epistemic facts and unlearning.
``budgets``          token/compute throttling, VRAM reservation, hyperparameter
                     tuning and the feedback/router loop.
``selfheal``         health probes, fault detection, atomic write/rollback.
``ui``               adaptive UI component generation and personalization.
``stress``           the multi-profile stress harness that exercises all of the
                     above and writes the execution report.
===================  ==========================================================

Nothing here reaches the network on its own, and nothing here asks for
approval: these are local, deterministic components. The two standing owner
gates (spend, Amazon) are enforced upstream by ``tys_assistant`` and by Chrome
Connect, not re-implemented here.
"""

__all__ = [
    "storage",
    "bridge",
    "validators",
    "memory",
    "budgets",
    "selfheal",
    "ui",
    "stress",
]
