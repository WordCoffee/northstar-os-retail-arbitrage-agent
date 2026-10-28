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

## 2. Applied — Owner Directive in the two protected files

**Commit `e077a4ed`** (`owner-authorized: Owner Directive 2026-10-28 in the capsule
and the constitution`).

```
 AGENTS.md                      | 57 ++++++++++++++++++++++++++++++++++
 docs/OPERATING_CONSTITUTION.md | 69 ++++++++++++++++++++++++++++++++++++++++++
 opencode.json                  |  2 --
 3 files changed, 126 insertions(+), 2 deletions(-)
```

`opencode.json` — exactly two lines removed, nothing else touched (36 rules remain;
every credential/secret deny stays):

```diff
-    { "action": "edit", "resource": "AGENTS.md", "effect": "deny" },
-    { "action": "edit", "resource": "docs/OPERATING_CONSTITUTION.md", "effect": "deny" },
```

Content added to both files: Tys Assistant as the admin-facing automation agent that
may run approved unattended bounded campaigns; **standing gates reduced to exactly
two** (money/paid credits, Amazon); denylist mode as the configured open-web mode;
Chrome Connect action-level protections explicitly retained; no permanent
self-granting, no policy bypasses, no secret disclosure.

`docs/OPERATING_CONSTITUTION.md` §3 (Guardrail Zone) additionally carries an
**AMENDED 2026-10-28** note so the old list cannot be read as still gating:
everything except the two gates is now an operating rule the model applies on its
own judgment. The credential-hygiene prohibition on disclosure/committing secrets
remains.

---

## 3. Controller reload — confirmed live

The MCP child had already respawned (pid 9168), so no kill was needed and Chrome was
never touched. The running controller now reports the **new** fingerprint:

```
fingerprint  46308c9bb48090d796906edfc5229bbfb6ca6994cdd7cc1ea257b301bac349d5
baseline     46308c9bb48090d796906edfc5229bbfb6ca6994cdd7cc1ea257b301bac349d5
intact       true
```

Policy surface verified against the module (no Amazon request made — these are
policy evaluations, evaluated before any transport):

```
BLOCK amazon_prohibited   amazon.com · sellercentral.amazon.com · amazon.co.uk
ALLOW open_web_denylist   github.com · huggingface.co · arxiv.org · 127.0.0.1:8000
BLOCK prohibited_action   enter_credentials · solve_captcha · purchase · checkout
BLOCK prohibited_action   account_settings · send_message
BLOCK external_state_change_requires_gate   submit_form_external
```

Profile 6 lease valid, `selected_directory_exact` and `display_name_exact` pass.

---

## 4. Live checks

| Check | Result |
|---|---|
| `rollback/pre-overnight-20261028` exists | PASS — tag + 11 DBs + 38 model manifest |
| Restorable | PASS — proven by a real restore (see §1.1) |
| **Fresh pre-campaign point** | **`pre-campaign-20261028`** @ `e077a4ed`, 11 DBs, 38 models |
| Backend health | 200; `/api/chat/sessions` **200 after 7.11 s** under a held write lock (busy-timeout fix live) |
| ComfyUI | 200 (`:8188`) |
| Bojo | `/api/ps` empty — unloaded, CPU-only |
| 27B worker | `:8080` closed, 0 `llama-server` processes — on demand |
| Vite `:8101` | was down; restarted |

---

## 5. BLOCKER — the campaign cannot start the browser lane

`chromeconnect_preflight` → `transport_profile_binding` FAILED,
`mcp_session_state: NO_SESSION`, `child_pid: null`,
`extension_relay_not_seen_yet`. A live run returns:

```
REFUSED  EXTENSION_RECONNECT_REQUIRED
The Playwright MCP extension in profile "Profile 6" did not answer after 1
reconnect attempt(s). Automatic recovery is exhausted (limit: one per run).
Operator action: click the Playwright extension in that Chrome window to
reconnect, then start a new run.
```

Cause: the Chrome Connect MCP server restarted (pid 22012 → 9168) and dropped the
extension relay. Reconnecting it needs **one click on the Playwright extension icon
in the Profile 6 window**. I cannot do that: the browser lane is the thing that is
down, and killing/relaunching Chrome is prohibited.

**This is the single operator action blocking T2 and every other Chrome Connect
item.** Everything upstream of it is ready. No campaign work order can produce a
UI acceptance until the relay answers.

---

## 6. Not started

Campaign priority 1–5 (T2, T4–T8/C5, creative defects, research backlog, FLUX swap)
— all gated behind §5. FLUX replacement correctly deferred: no FLUX 3 weights exist
on this box and no working render path has been proven.

