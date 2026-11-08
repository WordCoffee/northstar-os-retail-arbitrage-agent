"""RankLedger — real rank surface tests (gap-b).

RankLedger is not mounted in ``main.app``. Its real HTTP surface is the
foundation keyword router (``GET /api/v1/foundation/keywords/rank-history/{id}``)
and its real read layer is ``KeywordReadContracts`` in
``foundation/keywords/contracts.py``. Both are exercised here against a
disposable SQLite foundation state built by the real ``create_app`` factory.

The behaviour under test is RankLedger's core honesty rule: a rank that was
never observed is ``null``/absent, never fabricated and never turned into 0.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import jwt as pyjwt
import pytest

_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Placeholder values only; the ancestor conftest preserves "test-" values and
# never treats them as real credentials.
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("NS_FOUNDATION_BIND_HOST", "127.0.0.1")
os.environ.setdefault("NORTHSTAR_JWT_SECRET", "test-rankledger-hs256-not-real-0123456789abcdef")

from fastapi.testclient import TestClient  # noqa: E402

from foundation.api.state import FoundationState  # noqa: E402
from foundation.app import create_app  # noqa: E402
from foundation.enums import Role  # noqa: E402
from foundation.keywords.contracts import KeywordReadContracts  # noqa: E402
from foundation.models import (  # noqa: E402
    Keyword,
    Membership,
    Organization,
    RankObservation,
    User,
)

BASE = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)


def _bearer(user_id: str, org_id: str) -> dict:
    now = datetime.now(timezone.utc)
    token = pyjwt.encode(
        {
            "sub": user_id,
            "type": "access",
            "iat": now,
            "exp": now + timedelta(hours=1),
            "jti": f"sess_test_{user_id}",
            "tenant_id": org_id,
            "role": Role.ORGANIZATION_OWNER.value,
        },
        os.environ["NORTHSTAR_JWT_SECRET"],
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _keyword(repos, org_id: str, phrase: str, *, confidence: float = 1.0) -> dict:
    return repos.keywords.add(Keyword(
        organization_id=org_id,
        normalized_phrase=phrase,
        original_phrase=phrase.title(),
        marketplace="amazon.com",
        match_type="broad",
        confidence=confidence,
    ))


def _observation(repos, org_id: str, keyword_id: str, *, asin: str,
                 rank, placement: str, day: int) -> dict:
    return repos.rank_observations.add(RankObservation(
        organization_id=org_id,
        keyword_id=keyword_id,
        asin=asin,
        rank=rank,
        placement=placement,
        observed_at=BASE + timedelta(days=day),
        source="import",
    ))


@pytest.fixture()
def world(tmp_path):
    app = create_app(str(tmp_path / "rankledger.db"))
    state: FoundationState = app.state.foundation

    org = Organization(name="Acme Retail", slug="acme")
    other_org = Organization(name="Other Co", slug="other")
    user = User(email="owner@example.test", display_name="Owner")
    for repo, obj in ((state.repos.organizations, org),
                      (state.repos.organizations, other_org),
                      (state.repos.users, user)):
        repo.add(obj)
    state.repos.memberships.add(Membership(
        organization_id=org.id, user_id=user.id,
        role=Role.ORGANIZATION_OWNER.value))

    org_id = org.id
    main_kw = _keyword(state.repos, org_id, "dog leash")
    _observation(state.repos, org_id, main_kw["id"], asin="B0RANKORG1",
                 rank=12, placement="organic", day=0)
    _observation(state.repos, org_id, main_kw["id"], asin="B0RANKORG1",
                 rank=9, placement="organic", day=1)
    _observation(state.repos, org_id, main_kw["id"], asin="B0RANKORG1",
                 rank=4, placement="organic", day=2)

    # Observed but unknown: rank must stay null, never become 0.
    unknown_kw = _keyword(state.repos, org_id, "retractable leash")
    _observation(state.repos, org_id, unknown_kw["id"], asin="B0RANKUNK1",
                 rank=None, placement="organic", day=0)

    empty_kw = _keyword(state.repos, org_id, "leash for dogs")

    filter_kw = _keyword(state.repos, org_id, "leash clip")
    _observation(state.repos, org_id, filter_kw["id"], asin="B0RANKFLT2",
                 rank=8, placement="organic", day=0)
    _observation(state.repos, org_id, filter_kw["id"], asin="B0RANKFLT2",
                 rank=2, placement="sponsored", day=1)
    _observation(state.repos, org_id, filter_kw["id"], asin="B0RANKFLT3",
                 rank=30, placement="sponsored", day=2)

    other_kw = _keyword(state.repos, other_org.id, "cat harness")
    _observation(state.repos, other_org.id, other_kw["id"], asin="B0OTHERORG",
                 rank=1, placement="organic", day=0)

    result = SimpleNamespace(
        state=state,
        client=TestClient(app),
        org_id=org_id,
        user_id=user.id,
        headers=_bearer(user.id, org_id),
        main_kw=main_kw["id"],
        unknown_kw=unknown_kw["id"],
        empty_kw=empty_kw["id"],
        filter_kw=filter_kw["id"],
        other_kw=other_kw["id"],
    )
    try:
        yield result
    finally:
        state.close()


def test_rank_history_route_returns_persisted_series_in_time_order(world):
    resp = world.client.get(
        f"/api/v1/foundation/keywords/rank-history/{world.main_kw}",
        headers=world.headers)

    assert resp.status_code == 200
    items = resp.json()["items"]
    assert [row["rank"] for row in items] == [12, 9, 4]  # observed_at ASC
    assert all(row["keyword_id"] == world.main_kw for row in items)
    assert all(row["asin"] == "B0RANKORG1" for row in items)
    assert all(row["placement"] == "organic" for row in items)
    assert all(row["source"] == "import" for row in items)
    assert all(row["confidence"] is None for row in items)
    assert all(isinstance(row["observed_at"], str) for row in items)
    assert all(
        set(row) == {"id", "keyword_id", "asin", "rank", "placement",
                     "observed_at", "source", "confidence", "freshness_state"}
        for row in items)


def test_rank_history_keeps_unobserved_rank_null_and_missing_series_empty(world):
    # A stored observation with no measured rank stays null: never 0, never a guess.
    unknown = world.client.get(
        f"/api/v1/foundation/keywords/rank-history/{world.unknown_kw}",
        headers=world.headers).json()["items"]
    assert len(unknown) == 1
    assert unknown[0]["rank"] is None

    # A tracked keyword with no observations yields an empty series, not a fake row.
    empty = world.client.get(
        f"/api/v1/foundation/keywords/rank-history/{world.empty_kw}",
        headers=world.headers).json()["items"]
    assert empty == []

    # An unknown keyword id is likewise an empty series on this read path.
    missing = world.client.get(
        "/api/v1/foundation/keywords/rank-history/does-not-exist",
        headers=world.headers)
    assert missing.status_code == 200
    assert missing.json()["items"] == []


def test_rank_history_is_organization_scoped(world):
    # The other org's keyword exists and has a rank, but our org sees nothing.
    leaked = world.client.get(
        f"/api/v1/foundation/keywords/rank-history/{world.other_kw}",
        headers=world.headers)

    assert leaked.status_code == 200
    assert leaked.json()["items"] == []
    assert world.state.repos.rank_observations.for_keyword(
        world.org_id, world.other_kw) == []


def test_rank_history_requires_authentication(world):
    resp = world.client.get(
        f"/api/v1/foundation/keywords/rank-history/{world.main_kw}")

    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "authentication_required"


def test_rank_observation_filters_apply_and_compose(world):
    contracts = KeywordReadContracts(world.state.repos)

    by_asin = contracts.rank_observations(world.org_id, asin="B0RANKFLT2")
    assert len(by_asin) == 2
    assert {row["rank"] for row in by_asin} == {8, 2}

    by_placement = contracts.rank_observations(
        world.org_id, placement="sponsored")
    assert len(by_placement) == 2
    assert {row["rank"] for row in by_placement} == {2, 30}

    composed = contracts.rank_observations(
        world.org_id, asin="B0RANKFLT2", placement="sponsored")
    assert len(composed) == 1
    assert composed[0]["rank"] == 2

    limited = contracts.rank_observations(world.org_id, limit=1)
    assert len(limited) == 1

    # Another org's rows never enter this org's read.
    assert contracts.rank_observations(
        world.org_id, asin="B0OTHERORG") == []


def test_alert_conditions_flag_only_keywords_without_a_known_rank(world):
    contracts = KeywordReadContracts(world.state.repos)

    alerts = contracts.alert_conditions(world.org_id)
    flagged = {(a["keyword_id"], a["condition"]) for a in alerts}

    assert (world.unknown_kw, "rank_unknown") in flagged
    assert (world.empty_kw, "rank_unknown") in flagged
    # A keyword with a measured latest rank is not an alert condition.
    assert all(kw_id != world.main_kw for kw_id, _ in flagged)
    assert all(kw_id != world.filter_kw for kw_id, _ in flagged)
    # Another org's unknown-rank keyword is not this org's alert.
    assert all(kw_id != world.other_kw for kw_id, _ in flagged)

    phrases = {a["keyword_id"]: a["phrase"] for a in alerts}
    assert phrases[world.unknown_kw] == "retractable leash"
    assert phrases[world.empty_kw] == "leash for dogs"
