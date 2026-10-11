# Archive Credential Review — for the scrub decision

- **Date:** 2026-10-11 · **Owner:** T2 Holdings LLC · **Status:** review delivered; **scrub decision = owner** (per directive: decision comes after this review)
- **Security scan state (standing line):** **Active findings: 8** — 2 chat-archive credential values (this report), 1 `ghp_` token (revocation in progress), 1 `rate_limiter.py` review item; 231 reviewed-benign fingerprints allowlisted.
- **Method:** masked enumeration only — credential NAMES + value shape + `sha256_16` fingerprints; **no value was reproduced** in this report or its tooling.

## 1. Scope

| File | Lines | Notes |
|---|---|---|
| `FirstNorthstarautomationchat.md` | 3,943 | tracked; last touched 2026-08-11 (`a299d6e`) |
| `autothink-ui-chat-export.md` | 9,305 | tracked; carries the single `ghp_` finding |

## 2. Inventory (names/fingerprints only)

### FirstNorthstarautomationchat.md — two duplicated env blocks (L1142–1163 and L1290–1310)

**Credential material (the only two secrets):**

| Name | Lines | sha256_16 | Notes |
|---|---|---|---|
| `SCAVIO_API_KEY` | 1143, 1291 | `ca2d8a22d6f0d252` | `sk_`-style; same value in both blocks |
| `BRIGHTDATA_API_KEY` | 1148, 1296 | `f7f62b13a37f5afd` | GUID-style; same value in both blocks |

**Non-credential config in the same blocks (safe to keep):** `SCAVIO_API_URL`, `BRIGHTDATA_DATASET_ID`, `SEARCH_QUERY`, `SEARCH_KEYWORDS`, `COSTCO_CSV_PATH`, thresholds (`MIN_PROFIT_MARGIN_PERCENT`, `MIN_ROI_PERCENT`, `MAX_SELLER_RANK`), `PAGES_TO_SEARCH`, `PORT`, `DEFAULT_MARKETPLACE`. No other credential-shaped lines exist in this archive (full env-line enumeration + scanner + gitleaks agree).

### autothink-ui-chat-export.md
- No env-style credential lines at all.
- The single finding is the prose line quoting a GitHub PAT (`ghp_…`, sha256_16 `ef33331652fdc1f8`) — already escalated; **owner-side revocation in progress tonight**.

## 3. Assessment

- Posture: exactly **two credential names** × 2 duplicates in these archives; rotation is being handled owner-side **tonight (2026-10-11)**.
- After rotation completes, the exposed values become dead material; the residual risk is hygiene/reputation (dead keys preserved in a committed archive + in **git history**), not live access.
- The scanner keeps these values **ACTIVE** until the bytes are removed or the owner instructs an allowlist entry — by design (8 honest findings > a clean-looking scan).

## 4. Scrub options (choose one)

| Option | What it does | Pros | Cons |
|---|---|---|---|
| **A — Line-level redaction (recommended)** | Replace the 4 values (L1143/1148/1291/1296) with `[REDACTED]` in one reviewed commit per file; keep surrounding context | Minimal diff; archive stays readable; findings clear naturally (no allowlist needed); reversible via git | Values remain in git history (separate policy question) |
| B — File removal / replaced copy | Delete or replace both archives with redacted copies | Clean working tree | Loses operator archive context; larger diff; same history caveat |
| C — Keep as-is + fingerprint-allowlist after rotation | No file edits; add the two fingerprints to `.secret_scan_allowlist.json` with a "rotated" reason | Zero content change | Dead keys stay visible in the committed file; the scan shows them as "allowlisted" indefinitely |

**Recommendation: Option A.** It removes the live bytes, keeps the archive's value, and requires no allowlist entry — the finding simply stops existing.

## 5. Execution plan (when approved)

1. One commit: `FirstNorthstarautomationchat.md` — 4 line-level replacements (`SCAVIO_API_KEY=[REDACTED]`, `BRIGHTDATA_API_KEY=[REDACTED]` ×2 blocks).
2. If covered by the same decision: same treatment for the `ghp_` line in `autothink-ui-chat-export.md`.
3. Re-run `python -m northstar.security.secret_scan --tracked` → expected active count drops 8 → 4 (only `rate_limiter.py` + the not-yet-scrubbed items remain).
4. **History note:** the values also exist in committed history; working-tree redaction does NOT rewrite history. History rewrite remains a separate, owner-only decision (same policy as the 2026-09 `NO_LEAK_AUDIT` F2 item).

## 6. Adjacent material (owner-side, outside this repo — agent does not touch it)

`master-brain/README.md` records that the master-brain seed came from `C:\Users\T2Hol\Desktop\All AI Chat Markdowns` (16+ chat exports). These two archive findings are almost certainly duplicated there. **Recommend the same review/scrub for that folder** (owner-side); the rotation covers live risk, but the folder is likely to contain the same dead material.

---

**Standing line (repeat):** **Active findings: 8** — this report changes nothing by itself; the count only moves when rotation + scrub (or an owner-instructed allowlist entry) is executed.
