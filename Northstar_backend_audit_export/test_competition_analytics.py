"""Offline tests for seller-competition analytics (competition_analytics).

Covers the roster-state honesty rules: zero seller counts only under
explicit complete zero-offer evidence; every other empty/partial/
failed/unavailable roster is Unknown with a roster reason; observed
counts come only from actual returned offer rows; landed prices only
when the offer row supports them; and seller share requires both an
estimate and a positive observed denominator.
"""

import unittest

import competition_analytics as ca


def _offer(price, fba=False, fbm=False, prime=False, sba=False, seller="Seller Co", free=True):
    return {
        "position": 1,
        "price": {"value": price, "currency": "USD"},
        "seller_name": seller,
        "is_prime": prime,
        "is_fba": fba,
        "is_fbm": fbm,
        "is_sba": sba,
        "fulfilled_by_amazon": fba,
        "shipping_is_free": free,
    }


def _snapshot(status="available", offers=None, offers_returned=None, offers_complete=None,
             claimed=None, buy_box=None):
    return {
        "data_status": status,
        "offers": offers if offers is not None else [],
        "offers_returned": offers_returned,
        "offers_complete": offers_complete,
        "seller_counts": {"claimed_total": claimed, "observed_total": len(offers or []),
                          "fba_observed": sum(1 for o in (offers or []) if o.get("is_fba")),
                          "fbm_observed": sum(1 for o in (offers or []) if o.get("is_fbm")),
                          "amazon_observed": sum(1 for o in (offers or []) if o.get("is_sba")),
                          "counts_from_observed": True},
        "buy_box": buy_box or {},
    }


class RosterStateHonestyTests(unittest.TestCase):
    def test_available_without_offers_and_without_claimed_is_unknown(self):
        snap = _snapshot(status="available", offers=[], offers_returned=None,
                         offers_complete=None, claimed=None)
        fields = ca.competition_fields(snap, estimated_monthly_sales=1000)
        self.assertIsNone(fields["observed_total_sellers"])
        self.assertIsNone(fields["observed_fba_sellers"])
        self.assertIsNone(fields["observed_fbm_sellers"])
        self.assertIsNone(fields["observed_amazon_sellers"])
        self.assertEqual(fields["offer_roster_reason"], ca.REASON_NO_ZERO_EVIDENCE)
        self.assertIsNone(fields["estimated_units_per_observed_seller"])
        self.assertIsNone(fields["seller_share_confidence"])
        self.assertIsNone(fields["prime_offer_count"])
        self.assertIsNone(fields["fulfilled_by_amazon_offer_count"])

    def test_partial_with_zero_returned_is_unknown(self):
        snap = _snapshot(status="partial", offers=[], offers_returned=0,
                         offers_complete=False, claimed=12)
        fields = ca.competition_fields(snap, estimated_monthly_sales=1000)
        self.assertIsNone(fields["observed_total_sellers"])
        self.assertEqual(fields["offer_roster_reason"], ca.REASON_PARTIAL_ROSTER)
        self.assertIsNone(fields["estimated_units_per_observed_seller"])

    def test_failed_and_unavailable_are_unknown(self):
        for status in ("failed", "unavailable"):
            snap = _snapshot(status=status, offers=[], offers_returned=0, offers_complete=False, claimed=5)
            fields = ca.competition_fields(snap, estimated_monthly_sales=1000)
            self.assertIsNone(fields["observed_total_sellers"])
            self.assertEqual(fields["offer_roster_reason"], ca.REASON_ROSTER_UNAVAILABLE)
            self.assertIsNone(fields["observed_fba_sellers"])

    def test_explicit_zero_offer_evidence_allows_zeros(self):
        snap = _snapshot(status="available", offers=[], offers_returned=0,
                         offers_complete=True, claimed=0)
        self.assertTrue(ca.explicit_zero_offer_evidence(snap))
        fields = ca.competition_fields(snap, estimated_monthly_sales=1000)
        self.assertEqual(fields["observed_total_sellers"], 0)
        self.assertEqual(fields["observed_fba_sellers"], 0)
        self.assertEqual(fields["observed_fbm_sellers"], 0)
        self.assertEqual(fields["observed_amazon_sellers"], 0)
        self.assertEqual(fields["prime_offer_count"], 0)
        self.assertEqual(fields["fulfilled_by_amazon_offer_count"], 0)
        self.assertEqual(fields["seller_share_basis"], "complete zero-offer set")
        self.assertEqual(fields["seller_share_confidence"], "medium")
        self.assertIsNone(fields["estimated_units_per_observed_seller"])

    def test_zero_proof_requires_all_four_conditions(self):
        # Complete + claimed 0 but returned missing -> NOT proof.
        snap = _snapshot(status="available", offers=[], offers_returned=None,
                         offers_complete=True, claimed=0)
        self.assertFalse(ca.explicit_zero_offer_evidence(snap))
        fields = ca.competition_fields(snap)
        self.assertIsNone(fields["observed_total_sellers"])
        self.assertEqual(fields["offer_roster_reason"], ca.REASON_NO_ZERO_EVIDENCE)
        # available + claimed 0 + returned 0 but offers_complete missing -> NOT proof.
        snap2 = _snapshot(status="available", offers=[], offers_returned=0,
                          offers_complete=None, claimed=0)
        self.assertFalse(ca.explicit_zero_offer_evidence(snap2))
        fields2 = ca.competition_fields(snap2)
        self.assertIsNone(fields2["observed_total_sellers"])

    def test_partial_with_returned_rows_is_observed(self):
        snap = _snapshot(status="partial", offers=[_offer(49.99, fbm=True)],
                         offers_returned=1, offers_complete=False, claimed=12)
        fields = ca.competition_fields(snap, estimated_monthly_sales=1000)
        self.assertEqual(fields["observed_total_sellers"], 1)
        self.assertEqual(fields["observed_fbm_sellers"], 1)
        self.assertIsNone(fields.get("offer_roster_reason"))
        self.assertEqual(fields["seller_share_confidence"], "low")
        self.assertIn("sample", fields["seller_share_basis"])
        self.assertEqual(fields["offer_competition_note"], ca.PARTIAL_SAMPLE_WARNING)


class ObservedOfferTests(unittest.TestCase):
    def test_counts_and_prices_from_returned_rows_only(self):
        snap = _snapshot(
            status="available",
            offers=[_offer(56.66, fba=True, prime=True, sba=True, seller="Amazon"),
                    _offer(49.99, fbm=True, free=False)],
            offers_returned=2, offers_complete=True, claimed=2,
            buy_box={"available": True, "price": {"value": 56.66}, "seller_name": "Amazon",
                     "fulfillment": "Amazon"},
        )
        fields = ca.competition_fields(snap, estimated_monthly_sales=1000)
        self.assertEqual(fields["observed_total_sellers"], 2)
        self.assertEqual(fields["observed_fba_sellers"], 1)
        self.assertEqual(fields["observed_fbm_sellers"], 1)
        self.assertEqual(fields["observed_amazon_sellers"], 1)
        self.assertEqual(fields["prime_offer_count"], 1)
        self.assertEqual(fields["fulfilled_by_amazon_offer_count"], 1)
        self.assertEqual(fields["lowest_returned_offer_price"], 49.99)
        self.assertEqual(fields["highest_returned_landed_price"], 56.66)
        self.assertAlmostEqual(fields["returned_offer_price_spread"], 6.67)
        self.assertEqual(fields["observed_buy_box_price"], 56.66)
        self.assertEqual(fields["observed_buy_box_seller"], "Amazon")
        self.assertEqual(fields["seller_share_confidence"], "medium")
        self.assertEqual(fields["estimated_units_per_observed_fba_seller"], 1000.0)
        self.assertEqual(fields["estimated_units_per_observed_seller"], 500.0)
        self.assertIn("Estimated allocation only", fields["seller_share_note"])

    def test_observed_zero_prime_among_real_rows_is_real(self):
        snap = _snapshot(
            status="available",
            offers=[_offer(10.0, fbm=True, prime=False), _offer(12.0, fbm=True, prime=False)],
            offers_returned=2, offers_complete=True, claimed=2,
        )
        fields = ca.competition_fields(snap)
        self.assertEqual(fields["prime_offer_count"], 0)
        self.assertEqual(fields["fulfilled_by_amazon_offer_count"], 0)

    def test_landed_price_only_when_free_shipping(self):
        snap = _snapshot(
            status="available",
            offers=[_offer(49.99, fbm=True, free=True), _offer(55.00, fbm=True, free=False)],
            offers_returned=2, offers_complete=True, claimed=2,
        )
        fields = ca.competition_fields(snap)
        self.assertEqual(fields["lowest_returned_landed_price"], 49.99)
        self.assertEqual(fields["highest_returned_landed_price"], 49.99)

    def test_no_share_without_estimate(self):
        snap = _snapshot(
            status="available",
            offers=[_offer(49.99, fbm=True), _offer(56.66, fba=True)],
            offers_returned=2, offers_complete=True, claimed=2,
        )
        fields = ca.competition_fields(snap)
        self.assertIsNone(fields["estimated_units_per_observed_seller"])
        self.assertIsNone(fields["seller_share_confidence"])
        self.assertIsNone(fields["seller_share_basis"])

    def test_no_denominator_of_one_substitution(self):
        # est sales present but a fulfillment type has zero observed
        # sellers: the per-type share stays Unknown (never est/1).
        snap = _snapshot(
            status="available",
            offers=[_offer(49.99, fbm=True)],
            offers_returned=1, offers_complete=True, claimed=1,
        )
        fields = ca.competition_fields(snap, estimated_monthly_sales=1000)
        self.assertIsNone(fields["estimated_units_per_observed_fba_seller"])
        self.assertEqual(fields["estimated_units_per_observed_fbm_seller"], 1000.0)

    def test_unknown_roster_never_produces_share(self):
        snap = _snapshot(status="failed", offers=[], offers_returned=0,
                         offers_complete=False, claimed=0)
        fields = ca.competition_fields(snap, estimated_monthly_sales=1000)
        self.assertIsNone(fields["seller_share_confidence"])
        self.assertIsNone(fields["seller_share_basis"])
        self.assertIsNone(fields["estimated_units_per_observed_seller"])

    def test_buy_box_landed_only_when_supplied(self):
        snap = _snapshot(
            status="available",
            offers=[_offer(50.0, fbm=True)],
            offers_returned=1, offers_complete=True, claimed=1,
            buy_box={"available": True, "price": {"value": 50.0}, "landed_price": None},
        )
        fields = ca.competition_fields(snap)
        self.assertIsNone(fields["observed_buy_box_landed_price"])
        self.assertEqual(fields["observed_buy_box_price"], 50.0)
        snap2 = _snapshot(
            status="available",
            offers=[_offer(50.0, fbm=True)],
            offers_returned=1, offers_complete=True, claimed=1,
            buy_box={"available": True, "price": {"value": 50.0}, "landed_price": {"value": 52.0}},
        )
        fields2 = ca.competition_fields(snap2)
        self.assertEqual(fields2["observed_buy_box_landed_price"], 52.0)


if __name__ == "__main__":
    unittest.main()