"""P4-T2 identity ingest contract tests (SQLite)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from Northstar_backend.foundation.api.state import FoundationState
from Northstar_backend.foundation import ingest_identity as ing
from Northstar_backend.foundation.jobs_handlers import build_default_registry


def _db(tmp_path):
    return FoundationState.build(str(tmp_path / "f.db"))


def _artifact(run_id="run-1", **kw):
    base = {"run_id": run_id, "source": "pipeline_export", "observed_at": ing._now(),
            "pairs": [], "score_inputs": []}
    base.update(kw)
    return base


def test_matching_packs_kept_distinct(tmp_path):
    st = _db(tmp_path)
    try:
        db = st.db
        art = _artifact(score_inputs=[{
            "input_id": "i1", "pair_id": "p1", "asin": "B000000001",
            "supplier_pack": 6, "marketplace_pack": 6, "unit_count": 6,
            "net_quantity": 12.0, "package_dimensions": {"l": 1, "w": 2, "h": 3},
            "raw_claims": {"supplier": "6 pack"}, "observed_at": ing._now(),
            "pack_match_state": "MATCH"}])
        out = ing.ingest(db, art)
        assert out["ok"] and out["inputs_upserted"] == 1
        row = db.get("resale_score_inputs", {"input_id": "i1"})
        assert row["supplier_pack"] == 6 and row["marketplace_pack"] == 6
        assert row["unit_count"] == 6 and row["net_quantity"] == 12.0
        assert row["freshness_state"] == "OBSERVED"
    finally:
        st.close()


def test_true_mismatch_preserved(tmp_path):
    st = _db(tmp_path)
    try:
        db = st.db
        ing.ingest(db, _artifact(score_inputs=[{
            "input_id": "i2", "supplier_pack": 6, "marketplace_pack": 12,
            "unit_count": 12, "observed_at": ing._now(), "pack_match_state": "MISMATCH"}]))
        row = db.get("resale_score_inputs", {"input_id": "i2"})
        assert row["supplier_pack"] == 6 and row["marketplace_pack"] == 12
        import json
        assert json.loads(row["normalized_json"])["pack_match_state"] == "MISMATCH"
    finally:
        st.close()


def test_missing_packs_stay_unknown_freshness(tmp_path):
    st = _db(tmp_path)
    try:
        db = st.db
        ing.ingest(db, _artifact(score_inputs=[{"input_id": "i3"}]))
        row = db.get("resale_score_inputs", {"input_id": "i3"})
        assert row["supplier_pack"] is None and row["marketplace_pack"] is None
        assert row["freshness_state"] == "UNKNOWN"
    finally:
        st.close()


def test_stale_observation_is_cached(tmp_path):
    st = _db(tmp_path)
    try:
        db = st.db
        old = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        ing.ingest(db, _artifact(score_inputs=[{"input_id": "i4", "observed_at": old}]))
        assert db.get("resale_score_inputs", {"input_id": "i4"})["freshness_state"] == "CACHED"
    finally:
        st.close()


def test_pack_match_state_never_upgraded(tmp_path):
    st = _db(tmp_path)
    try:
        db = st.db
        ing.ingest(db, _artifact(score_inputs=[
            {"input_id": "u1", "pack_match_state": "UNKNOWN"},
            {"input_id": "u2", "pack_match_state": "garbage"},
            {"input_id": "u3", "pack_match_state": "MATCH"}]))
        import json
        assert json.loads(db.get("resale_score_inputs", {"input_id": "u1"})["normalized_json"])["pack_match_state"] == "UNKNOWN"
        assert json.loads(db.get("resale_score_inputs", {"input_id": "u2"})["normalized_json"])["pack_match_state"] == "UNKNOWN"
        assert json.loads(db.get("resale_score_inputs", {"input_id": "u3"})["normalized_json"])["pack_match_state"] == "MATCH"
    finally:
        st.close()


def test_invalid_asin_is_not_trusted(tmp_path):
    st = _db(tmp_path)
    try:
        db = st.db
        ing.ingest(db, _artifact(pairs=[{"pair_id": "p9", "asin": "not-an-asin", "match_state": "CANDIDATE"}]))
        assert db.get("identity_pairs", {"pair_id": "p9"})["asin"] is None
    finally:
        st.close()


def test_conflicting_claims_counted_and_first_kept(tmp_path):
    st = _db(tmp_path)
    try:
        db = st.db
        ing.ingest(db, _artifact(score_inputs=[{"input_id": "c1", "supplier_pack": 6}]))
        out2 = ing.ingest(db, _artifact(run_id="run-2",
                                        score_inputs=[{"input_id": "c1", "supplier_pack": 12}]))
        assert out2["conflicts"] == 1
        assert db.get("resale_score_inputs", {"input_id": "c1"})["supplier_pack"] == 6
    finally:
        st.close()


def test_repeated_ingestion_is_idempotent(tmp_path):
    st = _db(tmp_path)
    try:
        db = st.db
        art = _artifact(pairs=[{"pair_id": "p1", "asin": "B000000001", "match_state": "CANDIDATE"}],
                        score_inputs=[{"input_id": "i1", "supplier_pack": 6}])
        first = ing.ingest(db, art)
        again = ing.ingest(db, art)
        assert first["pairs_upserted"] == 1 and first["inputs_upserted"] == 1
        assert again["idempotent"] is True
        assert again["pairs_upserted"] == 1 and again["inputs_upserted"] == 1
        assert len(db.list("identity_pairs")) == 1
        assert len(db.list("resale_score_inputs")) == 1
    finally:
        st.close()


def test_unavailable_artifact_reported_not_fabricated(tmp_path):
    st = _db(tmp_path)
    try:
        db = st.db
        assert ing.ingest(db, {})["error"] == "missing_run_id"
        empty = ing.ingest(db, _artifact(run_id="empty"))
        assert empty["ok"] is True and empty["rows_in"] == 0
    finally:
        st.close()


def test_handler_registered_and_idempotent(tmp_path):
    reg = build_default_registry()
    assert reg.has("pipeline.ingest_identity") is True
    st = _db(tmp_path)
    try:
        h = reg.handler("pipeline.ingest_identity")
        art = _artifact(pairs=[{"pair_id": "hp", "asin": "B000000002", "match_state": "CANDIDATE"}])
        r1 = h({"artifact": art}, {"db": st.db})
        r2 = h({"artifact": art}, {"db": st.db})
        assert r1.ok and r2.ok
        assert r1.output["pairs_upserted"] == 1
        assert r2.output["idempotent"] is True
        missing = h({}, {"db": st.db})
        assert missing.ok is False and missing.error_code == "artifact_required"
    finally:
        st.close()