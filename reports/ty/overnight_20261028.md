# Ty overnight campaign — state after Phase 0

**Date:** 2026-10-28
**Directive:** Owner Directive 2026-10-28 (Ty powerhouse)
**Branch:** `feature/chrome-connect-3.0` @ `62075e2b` + working tree
**External policy repo:** `OneDrive\Documents\Default Project` @ `ac5616e` (main)

---

## 1. Delivered and verified

### 1.1 Rollback system — built, tested, proven

`scripts/ty_rollback.ps1` — `-Create <name>` | `-List` | `-Restore <name>`.

A rollback point captures: git tag `rollback/<name>`, every SQLite database
(db + wal + shm), `config/`, the **external** Chrome Connect config dir, a
manifest of installed model files (name + size + mtime, never the weights), the
uncommitted work as a patch, and the list of untracked paths.

**Point taken:** `rollback/pre-overnight-20261028` — 11 database files, 38 model
files, 52,937 KB patch, 6,607 untracked paths listed.

**Restore tested for real** in a scratch worktree, not assumed. The first test
*caught two bugs in the script itself*:

1. the database copy ran **before** `git checkout`, so the tracked 41.82 MB
   `northstar.db` was immediately overwritten by the tag's 700 KB committed copy;
2. a second, trailing `git checkout` from the original draft re-clobbered it.

Both fixed by moving the checkout first and deleting the duplicate. Retested:

```
northstar.db      41.82 MB
integrity         ok
chat_sessions     25      (live: 25)
chat_messages     117     (live: 117)
ds_assets         74      (live: 74)
```

A restore is itself reversible: `-Restore` takes a `pre-restore-<ts>` point before
it touches anything.

### 1.2 Open-web denylist policy — committed, verified

Commit `ac5616e` in the external repo, title
**`owner-authorized: open-web denylist policy`**, as the directive required.

- `policy.js` — `loadOwnerConfig()` reads `host_policy` (`denylist` |
  `allowlist`); anything unrecognised keeps `allowlist`, so a typo can never
  silently widen reach. `evaluateUrl()` short-circuits to
  `{allowed: true, reason: 'open_web_denylist'}` **after** the Amazon check.
  `HOST_POLICY` is folded into the `GUARDRAILS` digest so the mode itself is
  audited.
- `chromecontrol_policy_owner.json` — `host_policy: "denylist"`, version 3, and
  the `baseline_fingerprint` re-recorded in the same change via
  `policy-bless --operator`.

Module-level verification:

```
BLOCK  amazon_prohibited    https://www.amazon.com/dp/B000
BLOCK  amazon_prohibited    https://sellercentral.amazon.com/x
BLOCK  amazon_prohibited    https://amazon.co.uk/dp/x
ALLOW  open_web_denylist    https://github.com/trending
ALLOW  open_web_denylist    https://huggingface.co/models
ALLOW  open_web_denylist    https://news.ycombinator.com
ALLOW  open_web_denylist    https://example.org/anything
ALLOW  open_web_denylist    http://127.0.0.1:8101/ui/
fingerprint 46308c9bb48090d796906edfc5229bbfb6ca6994cdd7cc1ea257b301bac349d5
```

Action-level limits are deliberately untouched: credential entry, CAPTCHA,
purchase/checkout and external state changes are still enforced per action, which
is what stands between an open web and the owner's signed-in accounts.

---

## 2. Needs you (two items, both one edit each)

### 2.1 `AGENTS.md` and `docs/OPERATING_CONSTITUTION.md` are edit-denied

`opencode.json` denies `edit` on exactly these two files:

```json
{ "action": "edit", "resource": "AGENTS.md", "effect": "deny" },
{ "action": "edit", "resource": "docs/OPERATING_CONSTITUTION.md", "effect": "deny" },
```

The directive requires an additive "Owner Directive 2026-10-28" block in both.
**Remove or scope those two deny lines** and the block can be written; it is
drafted and ready. Nothing else in the permission list was touched.

### 2.2 The running controller still holds the old policy in memory

`chromeconnect_status` still reports `1f84d421…` (intact, old baseline) because
the MCP child process loaded `policy.js` at startup. The file on disk is correct
and the new baseline is `46308c9b…`. **The Chrome Connect controller needs to
reload once** (restart the controller session; Chrome itself untouched) before
the new reach takes effect and the guardrail check reads the new fingerprint.

---

## 3. Not started

Brains (gateway roles, GPU lock manager), research engine + knowledge base, the
five research jobs, FLUX swap, T2 close-out, Lion's Mane package, Packify-class
creator, self-improvement A/B, and the 14-hour loop itself.

Phase 0 was the prerequisite: without a tested rollback and a working policy,
an unattended run is exactly the thing that cannot be recovered from.
