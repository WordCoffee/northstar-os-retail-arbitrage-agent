"""Shared keyword/SEO read contracts (1C-05 / C09).

Read-only projections consumed by OfferChisel, Auctioneer, RankLedger, Town
Crier, AutothinK, and Master Brain. All are organization-scoped, provenance/
confidence/freshness-aware, and never fabricate data: unknown metrics stay
null.
"""
from __future__ import annotations

from typing import Optional

from ..repositories import Repositories


class KeywordReadContracts:
    def __init__(self, repos: Repositories) -> None:
        self.repos = repos

    # ------------------------------------------------------------------
    # OfferChisel — relevant keywords, listing coverage, gaps, intent
    # ------------------------------------------------------------------

    def relevant_keywords(self, org_id: str, *, query: Optional[str] = None,
                          limit: int = 50) -> list[dict]:
        rows = self.repos.keywords.list(
            where={"organization_id": org_id}, order_by="created_at DESC",
            limit=limit)
        if query:
            q = query.strip().lower()
            rows = [r for r in rows if q in (r.get("normalized_phrase") or "").lower()]
        return [self._kw_view(r, org_id) for r in rows]

    def listing_coverage(self, org_id: str, keyword_id: str) -> dict:
        kw = self.repos.keywords.get(keyword_id)
        if not kw or kw["organization_id"] != org_id:
            return {"covered": False, "links": [], "evidence": []}
        links = self.repos.keyword_links.list(
            where={"organization_id": org_id, "keyword_id": keyword_id})
        asins = sorted({l.get("asin") for l in links if l.get("asin")})
        return {"covered": bool(asins), "asins": asins,
                "links": links,
                "evidence": self._evidence(org_id, keyword_id)}

    def keyword_gaps(self, org_id: str, *, candidates: Optional[list[str]] = None,
                     limit: int = 50) -> list[dict]:
        """Keywords not yet targeted (no target row)."""
        keywords = self.repos.keywords.list(where={"organization_id": org_id})
        targets = self.repos.targets.list(where={"organization_id": org_id})
        targeted_ids = {t.get("keyword_id") for t in targets}
        gaps = [k for k in keywords if k["id"] not in targeted_ids]
        if candidates:
            gaps = [k for k in gaps
                    if (k.get("normalized_phrase") or "") in
                    {c.strip().lower() for c in candidates}]
        return [self._kw_view(k, org_id) for k in gaps[:limit]]

    def search_intent(self, org_id: str, keyword_id: str) -> dict:
        kw = self.repos.keywords.get(keyword_id)
        if not kw or kw["organization_id"] != org_id:
            return {"unknown": True}
        return {"keyword_id": keyword_id,
                "phrase": kw.get("normalized_phrase"),
                "match_type": kw.get("match_type"),
                "brand_terms": kw.get("brand_terms"),
                "unknown": False}

    # ------------------------------------------------------------------
    # Auctioneer — search terms, targets, performance, harvest/negation
    # ------------------------------------------------------------------

    def search_terms(self, org_id: str, *, limit: int = 200,
                     min_clicks: Optional[int] = None) -> list[dict]:
        rows = self.repos.search_terms.list(
            where={"organization_id": org_id}, order_by="impressions DESC",
            limit=limit)
        if min_clicks is not None:
            rows = [r for r in rows if (r.get("clicks") or 0) >= min_clicks]
        return [self._st_view(r) for r in rows]

    def target_performance(self, org_id: str, *, limit: int = 200) -> list[dict]:
        targets = self.repos.targets.list(where={"organization_id": org_id})
        perf = self.repos.ad_perf.for_org(org_id, limit=limit)
        by_campaign = {}
        for p in perf:
            key = (p.get("campaign_id"), p.get("ad_group_id"))
            agg = by_campaign.setdefault(key, {"impressions": 0, "clicks": 0,
                                               "orders": 0, "spend": 0, "revenue": 0})
            agg["impressions"] += p.get("impressions") or 0
            agg["clicks"] += p.get("clicks") or 0
            agg["orders"] += p.get("orders") or 0
            agg["spend"] += p.get("spend") or 0
            agg["revenue"] += p.get("revenue") or 0
        out = []
        for t in targets:
            agg = by_campaign.get((t.get("campaign_id"), t.get("ad_group_id")), {})
            out.append({"target_id": t["id"], "keyword_id": t.get("keyword_id"),
                        "campaign_id": t.get("campaign_id"),
                        "ad_group_id": t.get("ad_group_id"),
                        "match_type": t.get("match_type"),
                        "performance": agg})
        return out

    def harvest_candidates(self, org_id: str, *, min_orders: int = 1) -> list[dict]:
        """Search terms with orders but no active target (harvest candidates)."""
        terms = self.repos.search_terms.list(where={"organization_id": org_id})
        return [self._st_view(t) for t in terms
                if (t.get("orders") or 0) >= min_orders]

    def negation_candidates(self, org_id: str, *, max_orders: int = 0,
                            min_clicks: int = 20) -> list[dict]:
        """High-click, zero-order terms (negation candidates)."""
        terms = self.repos.search_terms.list(where={"organization_id": org_id})
        return [self._st_view(t) for t in terms
                if (t.get("clicks") or 0) >= min_clicks
                and (t.get("orders") or 0) <= max_orders]

    # ------------------------------------------------------------------
    # RankLedger — tracked terms, rank observations, historical series
    # ------------------------------------------------------------------

    def rank_history(self, org_id: str, keyword_id: str) -> list[dict]:
        return [self._rank_view(r) for r in
                self.repos.rank_observations.for_keyword(org_id, keyword_id)]

    def rank_observations(self, org_id: str, *, asin: Optional[str] = None,
                          placement: Optional[str] = None,
                          limit: int = 200) -> list[dict]:
        rows = self.repos.rank_observations.list(
            where={"organization_id": org_id}, order_by="observed_at DESC",
            limit=limit)
        if asin:
            rows = [r for r in rows if r.get("asin") == asin]
        if placement:
            rows = [r for r in rows if r.get("placement") == placement]
        return [self._rank_view(r) for r in rows]

    def alert_conditions(self, org_id: str) -> list[dict]:
        """Tracked terms with null/stale rank observations."""
        keywords = self.repos.keywords.list(where={"organization_id": org_id})
        alerts = []
        for kw in keywords:
            ranks = self.repos.rank_observations.for_keyword(org_id, kw["id"])
            latest = ranks[-1] if ranks else None
            if latest is None or latest.get("rank") is None:
                alerts.append({"keyword_id": kw["id"],
                               "phrase": kw.get("normalized_phrase"),
                               "condition": "rank_unknown"})
        return alerts

    # ------------------------------------------------------------------
    # Town Crier — approved themes / brand language / editorially controlled
    # ------------------------------------------------------------------

    def approved_themes(self, org_id: str, *, limit: int = 100) -> list[dict]:
        """Editorially controlled theme candidates: branded, high-confidence
        keywords with coverage. NOT auto-reused without context."""
        rows = self.repos.keywords.list(where={"organization_id": org_id})
        themed = []
        for kw in rows:
            links = self.repos.keyword_links.list(
                where={"organization_id": org_id, "keyword_id": kw["id"]})
            if kw.get("confidence") is not None and kw["confidence"] >= 0.8:
                themed.append({
                    "keyword_id": kw["id"],
                    "phrase": kw.get("normalized_phrase"),
                    "brand_terms": kw.get("brand_terms"),
                    "confidence": kw.get("confidence"),
                    "coverage": bool(links),
                    "requires_human_review": True,
                })
        return themed[:limit]

    def brand_language_guidance(self, org_id: str) -> dict:
        brands = {}
        for kw in self.repos.keywords.list(where={"organization_id": org_id}):
            for b in kw.get("brand_terms") or []:
                brands.setdefault(b, {"count": 0, "phrases": []})
                brands[b]["count"] += 1
                brands[b]["phrases"].append(kw.get("normalized_phrase"))
        return {"brands": brands,
                "note": "editorial guidance only; no automatic reuse without context"}

    # ------------------------------------------------------------------
    # AutothinK / Master Brain — authorized graph search
    # ------------------------------------------------------------------

    def graph_search(self, org_id: str, *, term: Optional[str] = None,
                     asin: Optional[str] = None,
                     limit: int = 50) -> dict:
        """Authorized graph search with provenance/confidence/freshness."""
        keywords = self.repos.keywords.list(where={"organization_id": org_id})
        if term:
            t = term.strip().lower()
            keywords = [k for k in keywords
                        if t in (k.get("normalized_phrase") or "").lower()]
        nodes = []
        for kw in keywords[:limit]:
            links = self.repos.keyword_links.list(
                where={"organization_id": org_id, "keyword_id": kw["id"]})
            if asin and not any(l.get("asin") == asin for l in links):
                continue
            nodes.append({
                "keyword_id": kw["id"],
                "phrase": kw.get("normalized_phrase"),
                "match_type": kw.get("match_type"),
                "marketplace": kw.get("marketplace"),
                "confidence": kw.get("confidence"),
                "freshness_state": kw.get("freshness_state"),
                "provenance": "imported_local" if kw.get("created_at") else "unknown",
                "links": links,
            })
        return {"nodes": nodes, "organization_scoped": True,
                "note": "local/imported data only; no live provider calls"}

    # ------------------------------------------------------------------
    # views
    # ------------------------------------------------------------------

    def _kw_view(self, kw: dict, org_id: str) -> dict:
        targets = self.repos.targets.list(
            where={"organization_id": org_id, "keyword_id": kw["id"]})
        links = self.repos.keyword_links.list(
            where={"organization_id": org_id, "keyword_id": kw["id"]})
        return {
            "id": kw["id"], "normalized_phrase": kw.get("normalized_phrase"),
            "original_phrase": kw.get("original_phrase"),
            "match_type": kw.get("match_type"), "marketplace": kw.get("marketplace"),
            "brand_terms": kw.get("brand_terms"), "confidence": kw.get("confidence"),
            "freshness_state": kw.get("freshness_state"),
            "target_count": len(targets), "link_count": len(links),
            "provenance": "imported_local",
        }

    @staticmethod
    def _st_view(st: dict) -> dict:
        return {
            "id": st["id"], "raw_term": st.get("raw_term"),
            "normalized_term": st.get("normalized_term"),
            "marketplace": st.get("marketplace"),
            "search_volume": st.get("search_volume"),
            "observed_volume": st.get("observed_volume"),
            "impressions": st.get("impressions"), "clicks": st.get("clicks"),
            "spend": st.get("spend"), "orders": st.get("orders"),
            "revenue": st.get("revenue"), "source": st.get("source"),
        }

    @staticmethod
    def _rank_view(r: dict) -> dict:
        return {
            "id": r["id"], "keyword_id": r.get("keyword_id"), "asin": r.get("asin"),
            "rank": r.get("rank"), "placement": r.get("placement"),
            "observed_at": r.get("observed_at"), "source": r.get("source"),
            "confidence": r.get("confidence"),
            "freshness_state": r.get("freshness_state"),
        }

    def _evidence(self, org_id: str, keyword_id: str) -> list[dict]:
        ranks = self.repos.rank_observations.for_keyword(org_id, keyword_id)
        return [self._rank_view(r) for r in ranks[-5:]]