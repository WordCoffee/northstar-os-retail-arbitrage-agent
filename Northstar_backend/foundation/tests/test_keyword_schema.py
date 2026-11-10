"""1C-05 keyword schema tests (C01).

Asserts the additive keyword/SEO schema objects exist in the single SCHEMA
source of truth, are created on SQLite, and that repository round-trips work.
PostgreSQL parity is covered by the migration harness + durable PG modules.
"""
from __future__ import annotations

import sqlite3

from Northstar_backend.foundation.db import SCHEMA, SQLITE_DDL
from Northstar_backend.foundation.db import FoundationDB
from Northstar_backend.foundation.repositories import Repositories
from Northstar_backend.foundation.models import (
    Organization, User, Membership, Keyword, SearchTerm, Target, KeywordLink,
    ImportBatch, SourceFile, SourceRow, RejectedRow, RankObservation,
    AdPerformanceObservation, KeywordConflict,
)
from Northstar_backend.foundation.enums import Role


KEYWORD_TABLES = [
    "keywords", "search_terms", "targets", "keyword_links", "import_batches",
    "source_files", "source_rows", "rejected_rows", "normalization_decisions",
    "rank_observations", "ad_performance_observations", "keyword_conflicts",
]


def test_keyword_tables_declared():
    for t in KEYWORD_TABLES:
        assert t in SCHEMA, f"missing {t}"


def test_keyword_tables_created_on_sqlite():
    con = sqlite3.connect(":memory:")
    try:
        for stmt in SQLITE_DDL:
            con.execute(stmt)
        for t in KEYWORD_TABLES:
            info = con.execute(f"PRAGMA table_info({t})").fetchall()
            assert info, f"table {t} not created"
    finally:
        con.close()


def test_keyword_columns_separate_search_terms_from_targets():
    kw = {c for c, _ in SCHEMA["keywords"]}
    st = {c for c, _ in SCHEMA["search_terms"]}
    tg = {c for c, _ in SCHEMA["targets"]}
    assert "normalized_phrase" in kw and "match_type" in kw
    assert "search_volume" in st and "observed_volume" in st
    assert "keyword_id" in tg and "campaign_id" in tg and "ad_group_id" in tg


def test_org_scoped_uniqueness_declared():
    from Northstar_backend.foundation.db import UNIQUE_COLUMNS
    assert ("organization_id", "normalized_phrase", "match_type", "marketplace") \
        in UNIQUE_COLUMNS["keywords"]
    assert ("organization_id", "file_sha256") in UNIQUE_COLUMNS["source_files"]
    assert ("organization_id", "normalized_term", "marketplace") \
        in UNIQUE_COLUMNS["search_terms"]


def test_keyword_repository_roundtrip():
    db = FoundationDB()
    try:
        repos = Repositories(db)
        org = Organization(name="KW Org", slug="kw-org")
        user = User(email="kw@example.test")
        db.insert("organizations", {"id": org.id, "name": org.name,
                                    "slug": org.slug, "environment": "sandbox",
                                    "active": 1, "created_at": org.created_at.isoformat()})
        db.insert("users", {"id": user.id, "email": user.email,
                            "display_name": user.display_name, "active": 1,
                            "created_at": user.created_at.isoformat()})
        db.insert("memberships", {"id": __import__("uuid").uuid4().hex,
                                  "organization_id": org.id, "user_id": user.id,
                                  "role": Role.ORGANIZATION_OWNER.value,
                                  "status": "active",
                                  "created_at": org.created_at.isoformat()})

        kw = Keyword(organization_id=org.id, normalized_phrase="dog leash",
                     original_phrase="Dog Leash", match_type="exact",
                     brand_terms=["Acme"])
        repos.keywords.add(kw)
        assert repos.keywords.by_phrase(org.id, "dog leash", "exact",
                                        "amazon.com") is not None

        st = SearchTerm(organization_id=org.id, raw_term="dog leash",
                        normalized_term="dog leash", search_volume=None)
        repos.search_terms.add(st)
        assert repos.search_terms.by_term(org.id, "dog leash", "amazon.com") is not None

        tg = Target(organization_id=org.id, keyword_id=kw.id, match_type="exact")
        repos.targets.add(tg)
        repos.keyword_links.add(KeywordLink(organization_id=org.id,
                                            keyword_id=kw.id, link_kind="product",
                                            asin="B0EXAMPLE"))
        src = SourceFile(organization_id=org.id, file_name="search-terms.csv",
                         file_sha256="a" * 64, report_type="search_term")
        repos.source_files.add(src)
        batch = ImportBatch(organization_id=org.id, source_file_id=src.id)
        repos.import_batches.add(batch)
        repos.source_rows.add(SourceRow(organization_id=org.id,
                                        import_batch_id=batch.id, row_index=0,
                                        row_json={"term": "dog leash"}, status="accepted"))
        repos.rejected_rows.add(RejectedRow(organization_id=org.id,
                                            import_batch_id=batch.id, row_index=1,
                                            row_json={"term": ""},
                                            rejection_reason="missing_term"))
        repos.rank_observations.add(RankObservation(organization_id=org.id,
                                                    keyword_id=kw.id,
                                                    asin="B0EXAMPLE",
                                                    rank=None, placement="organic"))
        repos.ad_perf.add(AdPerformanceObservation(organization_id=org.id,
                                                   search_term_id=st.id))
        repos.keyword_conflicts.add(KeywordConflict(
            organization_id=org.id, keyword_id_a=kw.id,
            keyword_id_b=kw.id, conflict_type="duplicate"))
        assert len(repos.source_rows.for_batch(batch.id)) == 1
        assert len(repos.rejected_rows.for_batch(batch.id)) == 1
    finally:
        db.close()


def test_null_rank_and_null_search_volume_preserved():
    db = FoundationDB()
    try:
        repos = Repositories(db)
        org = Organization(name="Null Org", slug="null-org")
        db.insert("organizations", {"id": org.id, "name": org.name,
                                    "slug": org.slug, "environment": "sandbox",
                                    "active": 1, "created_at": org.created_at.isoformat()})
        kw = Keyword(organization_id=org.id, normalized_phrase="x", match_type="broad")
        repos.keywords.add(kw)
        st = SearchTerm(organization_id=org.id, raw_term="x", normalized_term="x",
                        search_volume=None)
        repos.search_terms.add(st)
        ro = RankObservation(organization_id=org.id, keyword_id=kw.id,
                             rank=None, placement="organic")
        repos.rank_observations.add(ro)
        got = repos.rank_observations.for_keyword(org.id, kw.id)[0]
        assert got["rank"] is None
        got_st = repos.search_terms.by_term(org.id, "x", "amazon.com")
        assert got_st["search_volume"] is None  # unknown stays unknown
    finally:
        db.close()