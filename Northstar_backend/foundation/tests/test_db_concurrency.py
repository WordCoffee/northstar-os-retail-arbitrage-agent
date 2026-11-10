"""Regression: ONE foundation connection, many request threads.

Live origin (2026-10-18): the SPA issues its identity context calls in parallel
(``/api/v1/foundation/me`` + ``/environment`` + ``/preview/active``), and FastAPI
runs synchronous endpoints in a worker threadpool - so several threads reached a
single ``sqlite3`` connection at once. CPython's sqlite3 keeps a per-connection
statement cache, and concurrent statement creation on one connection raises
``InterfaceError: bad parameter or other API misuse``, which surfaced as HTTP 500
on ``/me`` and left the operator unable to stay signed in.

``FoundationDB`` now serializes every statement through ``_SerializedConnection``
and holds ``FoundationDB.lock`` across multi-statement transactions. This test
drives concurrent readers and writers through the repository-facing API; before
the fix it failed within a few hundred iterations.
"""
from __future__ import annotations

import threading

from Northstar_backend.foundation.db import FoundationDB

THREADS = 8
ITERATIONS = 200


def test_concurrent_reads_and_writes_raise_nothing(tmp_path) -> None:
    db = FoundationDB(str(tmp_path / "foundation.db"))
    try:
        db.insert("organizations", {
            "id": "org-1", "name": "T2 Holdings LLC", "slug": "t2-holdings-llc"})

        errors: list[str] = []
        barrier = threading.Barrier(THREADS)

        def worker(n: int) -> None:
            try:
                barrier.wait(timeout=30)
                for i in range(ITERATIONS):
                    assert db.get("organizations", {"id": "org-1"}) is not None
                    assert db.list("organizations", {"slug": "t2-holdings-llc"})
                    assert db.count("organizations") >= 1
                    db.insert_ignore("memberships", {
                        "id": f"m-{n}-{i}", "organization_id": "org-1",
                        "user_id": f"u-{n}", "role": "operator", "status": "active"})
            except Exception as exc:  # noqa: BLE001 - reported, never hidden
                errors.append(f"{type(exc).__name__}: {exc}")

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=120)
        for t in threads:
            assert not t.is_alive()

        assert errors == [], errors[:3]
        # Every write landed exactly once (no lost or duplicated inserts).
        assert db.count("memberships") == THREADS * ITERATIONS
    finally:
        db.close()


def test_multi_statement_transaction_is_not_interleaved(tmp_path) -> None:
    """atomic_claim_job holds the lock across BEGIN IMMEDIATE .. COMMIT."""
    db = FoundationDB(str(tmp_path / "foundation.db"))
    try:
        db.insert("organizations", {"id": "org-1", "name": "T2 Holdings LLC",
                                    "slug": "t2-holdings-llc"})
        db.insert("job_requests", {"id": "jq-1", "organization_id": "org-1",
                                   "service": "scout"})
        db.insert("job_runs", {"id": "jr-1", "job_request_id": "jq-1",
                               "state": "queued"})

        results: list[list] = []
        errors: list[str] = []
        barrier = threading.Barrier(4)

        def claim(worker_id: str) -> None:
            try:
                barrier.wait(timeout=30)
                results.append(db.atomic_claim_job(
                    worker_id=worker_id, organization_id="org-1",
                    lease_seconds=60, now_iso="2026-10-18T00:00:00+00:00"))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{type(exc).__name__}: {exc}")

        threads = [threading.Thread(target=claim, args=(f"w{n}",)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        assert errors == [], errors[:3]
        # Exactly one worker may claim the single queued run.
        assert sum(len(r) for r in results) == 1, results
    finally:
        db.close()
