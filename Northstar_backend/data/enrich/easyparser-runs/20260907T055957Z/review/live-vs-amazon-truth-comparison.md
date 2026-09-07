# Live vs. Amazon-Truth Comparison — run 20260907T055957Z

CLI evidence: `manifest-20260907T061811Z-98b7` · provider **easyparser** (OFFER) · **9/10** requests made, `stop_reason=max_credits` · credits reported **225** (cap 200).

| asin | csv title | live title (truncated) | price csv → live | Δ% | reviews csv→live | prime csv→live | BSR csv→live | title_review | discrepancy_class |
|---|---|---|---|---|---|---|---|---|---|
| B01H40O42I | Aller-Flo (Pack of 5) | Kirkland Signature Kirkland Aller-Flo Fluticasone Propio | 26.74 → 26.99 | +0.9% | 11114 → Unknown | Yes → FBM | n/a → n/a | match_confirmed_semantically | title_label_only_prime_mismatch |
| B08R2SRN88 | Aller-Flo (5 Bottles/600 sprays) | Kirkland Signature Aller-Flo Fluticasone Propionate (Glu | 26.8 → 26.8 | +0.0% | 11898 → Unknown | Yes → FBM | 3567 → n/a | match_confirmed_semantically | title_label_only_prime_mismatch |
| B0CP6LXPLK | Minoxidil Extra Strength (6-mo) | Minoxidil Liquid Extra Strength Hair Regrowth Treatment  | 33.12 → 15.29 | -53.8% | 1434 → Unknown | Yes → FBM | 2300 → n/a | match_confirmed_semantically | major_price_delta_prime_mismatch |
| B00BISGJXA | Stool Softener 100mg (400ct) | Kirkland Signature Stool Softener 100 mg, 400 Softgels | 12.75 → 11.17 | -12.4% | 18629 → Unknown | Yes → FBM | 4960 → n/a | match_confirmed_semantically | moderate_price_delta_prime_mismatch |
| B00BH3HPZW | Fiber Capsules (360ct) | Fiber Capsules Kirkland Therapy for Regularity/Fiber Sup | 17.84 → 17.66 | -1.0% | 4799 → Unknown | Yes → Prime | 6602 → n/a | match_confirmed_semantically | title_label_only |
| B00GYZWNY6 | Glucosamine 1500/Chondroitin 1200 (220ct) | Kirkland Extra Strength Glucosamine 1500 mg Chondroitin  | 29.25 → 29.25 | +0.0% | 5183 → Unknown | Yes → Prime | 6562 → n/a | match_confirmed_semantically | title_label_only |
| B0045XGE9E | Sleep Aid Doxylamine (2pk/192ct) | Kirkland Signature Sleep Aid Doxylamine Succinate 25 Mg, | 13.84 → 12.39 | -10.5% | 4966 → Unknown | Yes → FBM | 7570 → n/a | match_confirmed_semantically | moderate_price_delta_prime_mismatch |
| B002L4M4M0 | Sleep Aid Doxylamine (96ct) | KIRKLAND SIGNATURE Sleep Aid Doxylamine Succinate 25 Mg  | 7.93 → 7.93 | +0.0% | 6270 → Unknown | Yes → Prime | 14653 → n/a | match_confirmed_semantically | title_label_only |
| B081THWMDK | Stretch Tite Food Wrap (2pk) | Kirkland Signature Stretch Tite Plastic Food Wrap 11 7/8 | 28.79 → 23.98 | -16.7% | 967 → Unknown | Yes → FBM | n/a → n/a | match_confirmed_semantically | major_price_delta_prime_mismatch |
| B085F1QCB9 | Compactor Trash Bag |  | 28.07 → None | n/a | 588 → Unknown | No (Amazon-shipped, non-Prime badge) → Unknown | 11435 → n/a | no_live_data | skipped_no_call |

Notes: Easyparser OFFER does not supply review counts or BSR — `Unknown` / `n/a` are honest absences, never zero-filled. `mapping_error` = 0 for all invoked ASINs. B085F1QCB9 had **no provider call** (credit cap reached first). No purchase authorization.

Discrepancy classes: {"major_price_delta_prime_mismatch": 2, "moderate_price_delta_prime_mismatch": 2, "skipped_no_call": 1, "title_label_only": 3, "title_label_only_prime_mismatch": 2}