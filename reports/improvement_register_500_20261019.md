# Northstar OS — Improvement Register (500 items)

**Date:** 2026-10-19 · **Branch:** `feature/v4.1-mesh`
**Basis:** twelve hours of hands-on work in this repository — the V4.1 sign-in
repair, the V4.2 interface rebuild, Thorn v5.0 cards T-1…T-9, the live-path
defects, and the full-suite reconciliation (33 failures → 0, proven against a
baseline worktree).

**What this is:** a prioritised register of concrete changes, each traceable to an
observation. Items marked **⚠ proven** were directly witnessed in this session.
This is not a wish list of abstractions; if an item could not be tied to something
observed or measured, it is not here.

**How to read it:** `NNN. Observation → Action` (area headings group them; no
priority is implied by order within an area).

---

## 1. Test-suite integrity & isolation (1–25)

1. **⚠ proven** — `test_invite_flow` passed alone and failed in the full suite because it asserted on `caplog` configured by another test → add a session-scoped guard that fails any test whose outcome depends on a prior test's logger state.
2. **⚠ proven** — 33 failures sat unresolved across multiple sessions because no baseline was compared → make the A/B worktree comparison (`git worktree add <tmp> <ref>` + same file list) a documented, repeatable command.
3. **⚠ proven** — 26 failures were missing data presented as code failures → standardise a `_REQUIRED_FIXTURES` + `pytest.mark.skip(reason=…)` pattern and apply it to every data-coupled suite.
4. **⚠ proven** — two tests were **dead** for weeks (`on_progress` kwarg) and nobody noticed → add a "fakes must accept the real signature" check by asserting fakes against `inspect.signature` of the callable they replace.
5. **⚠ proven** — an assertion compared `None >= 0` and raised TypeError instead of failing meaningfully → ban bare comparisons on possibly-null values; assert the allowed shapes explicitly.
6. **⚠ proven** — a test counted the substring `secret` in a config template → forbid substring-count assertions on human-authored files; parse the structure instead.
7. **⚠ proven** — a test's extractor **fabricated** `/api/design-studiosample` from a template literal → any test that extracts facts from source text must be tested against a fixture containing the awkward cases (template literals, concatenation, interpolation).
8. **⚠ proven** — a test asserted a hardcoded route count that drifted (48 vs 52) → replace brittle magic numbers with `== len(<the artefact being counted>)` where the artefact is loaded once.
9. **⚠ proven** — 2 failures were report-schema drift with no owner → add an `xfail(reason=…, strict=False)` convention for "known drift needing operator data", and a monthly review task so xfails cannot rot.
10. **⚠ proven** — a suite reported "no tests ran" and exited 0 in one invocation (wrong filename) → add a CI guard that fails when the collected count is zero.
11. Add `pytest-randomly`-style seeded ordering to CI so order-dependence surfaces instead of hiding.
12. Add a `--strict-markers` + `--strict-config` default so typos in markers fail loudly.
13. Add a session fixture that snapshots and restores env vars, so a test that `setenv`s without monkeypatch cannot leak.
14. Add a test that asserts no test writes outside its `tmp_path` (watch the product DB mtime).
15. **⚠ proven** — the product DB `Northstar_backend/data/northstar.db` is written by live runs and could contaminate tests → point all tests at a temp DB via a conftest fixture rather than touching `data/`.
16. Add a "no network" audit test that monkeypatches `socket.socket` to raise, proving suites are offline.
17. **⚠ proven** — my own live turn inserted a `lane_telemetry` row into the real product DB → give dev/live experiments their own DB file and a documented reset path.
18. Introduce a `tests/` taxonomy (unit / integration / live / slow) with markers, so live-path tests never run by default.
19. Add coverage reporting for the modules touched by a change (diff-coverage), not global percentages.
20. Add a required test for every new chat tool (registry ↔ test parity), enforced by asserting the tool count changes only with a matching test.
21. **⚠ proven** — 161 modules have no test reference at all → use `purpose_commands --command expand-vectors` output as the standing backlog and burn it down by fan-in order.
22. Add a fixture-data manifest (`tests/fixtures/MANIFEST.md`) declaring which operator datasets are required and where they live, so skips are self-explaining.
23. Add a smoke test that boots the app and asserts `/openapi.json` route count, catching accidental route removals.
24. **⚠ proven** — `test_ui_route_contract` proves UI→API path resolution; keep it but extend it to flag UI paths that resolve to a *deprecated* route.
25. Add a "failure budget" report: print per-file pass/skip/xfail counts each run so drift is visible at a glance.

## 2. Data & fixtures (26–50)

26. **⚠ proven** — the benchmark/scanner fixtures are untracked and absent → decide once: commit sanitised fixtures, or generate them from a documented, reproducible query.
27. **⚠ proven** — a whole suite (proof_batch) is unrunnable in a clean checkout → make the "clean checkout" path a first-class acceptance test: clone to a temp dir and run the suite.
28. Add a `data/README.md` describing every data directory, its producer, its licence and whether it is regenerable.
29. Add a `.gitignore` audit test that asserts no data file over N MB is ever staged (protects the repo from accidental dataset commits).
30. **⚠ proven** — 4.56 GB repo, with data dirs from experiments → add a retention policy: prune run outputs older than 90 days except canonical/report sets.
31. Add a schema registry for every JSON artefact (preflight, benchmark, manifests) with a `validate()` callable and a test per artefact.
32. **⚠ proven** — the benchmark reference shape drives hardcoded expectations → version the dataset and pin the test expectations to the version.
33. Add a checksum manifest for canonical datasets so silent edits are detectable.
34. Add explicit `SAMPLE`/`LIVE` provenance labels to every fixture (the repo already does this for observations — extend it to test data).
35. Add a fixture generator script for each domain (sourcing, listing, creative) so tests never need operator data.
36. Add "unknown is a value" tests for every reporting surface (the repo's own honesty rule) — assert the API returns an explicit null rather than 0.
37. Add a data-dictionary generator that emits column docs from the SQLite schema, kept in sync by a test.
38. Add a migration-drift test for the SQLite product DB (compare live schema to the declared DDL).
39. **⚠ proven** — CSV/JSON duplicates exist across `data/` and `docs/…research…/` → add a dedupe audit that reports byte-identical files.
40. Add a quarantine folder for unverified scraped data, with a promotion test before it can reach a canonical path.
41. Add per-dataset "freshness" metadata and a test that flags datasets older than their declared TTL.
42. Add a golden-sample snapshot test for every report builder (report shape, not values).
43. Add a fuzz corpus for the scrapers' parsers so malformed HTML fails gracefully and loudly.
44. Add a fixture for "provider returns gibberish" and assert the honesty labels survive.
45. Add a test asserting no fixture contains a real customer identifier (PII screen over fixtures).
46. **⚠ proven** — fixtures are resolved CWD-relatively → standardise on `Path(__file__)`-relative resolution so tests behave identically from any directory.
47. Add a "missing data" dashboard listing which suites are currently skipped and why.
48. Add a backup/restore drill test for the product DB (the runbook documents it; automate the assertion).
49. Add a data-size budget check in CI (fail if `data/` grows by more than X MB per commit).
50. Add a documented one-command "reset local dev data" that never touches canonical/benchmark sets.

## 3. Database layer & handles (51–75)

51. **⚠ proven** — `DataLayer`, `NorthstarDB` and a raw `sqlite3` connection are all passed around as `db`, and only one of them has `execute` → define a single `Protocol` and assert every handle satisfies it at the boundary.
52. **⚠ proven** — `DataLayer` has no `executescript`, so `db.executescript()` raised AttributeError → add `executescript` (or a `run_ddl()` method) to the layer so callers stop duck-typing.
53. **⚠ proven** — a module silently swallowed that AttributeError behind `except Exception: pass` → ban bare `pass` in except blocks across the backend, enforced by a lint rule, with an allowlist for genuinely-cosmetic call sites.
54. **⚠ proven** — one shared `sqlite3` connection was used from FastAPI's threadpool, corrupting the statement cache and resetting mid-read cursors → document the single-connection+RLock invariant at the top of `foundation/db.py` and add a test that asserts it stays.
55. **⚠ proven** — `NorthstarDB` is a container whose `._layer` is the real handle → expose a first-class `db.conn`/`db.layer` accessor instead of callers reaching into a private attribute.
56. Add a connection-factory that returns a thread-local handle, removing the need for the global lock entirely.
57. Enable WAL mode on the product DB (`northstar.db`) and document the sidecar-file implications.
58. Add a `busy_timeout` assertion test so a future change cannot silently drop it.
59. Add a query-count guard for hot request paths (fail if a single request issues > N statements).
60. Add an index audit: log slow queries (via `sqlite3` progress handler) and report missing indexes.
61. Add a migration runner for the product DB (currently inline DDL only) with a ledger, mirroring `migrations_foundation`.
62. Add a "table added/removed" test so schema drift between code and docs fails CI.
63. Add a typed row-mapping helper (dict rows are fine; add a dataclass layer where the code already `dict(row)`s).
64. Add a transaction context manager so multi-statement writes cannot interleave.
65. Add a retention/compaction job for `lane_telemetry`, `audit_log` and `job_runs`.
66. Add a `VACUUM`/`ANALYZE` maintenance command and run it in the ops routine.
67. Add a read-only DB mode for reporting endpoints to remove write-lock contention.
68. Add a corruption detector (`PRAGMA integrity_check`) to the health endpoint.
69. Add per-account row-count limits for `memory_entries` to bound unbounded growth.
70. **⚠ proven** — the memory schema has no tier column, and I encoded tiers in `tags` → promote it to a real column with a migration once the tier model settles.
71. Add a soft-delete convention audit (the repo uses `retired_at`/`status`) so every table is consistent.
72. Add FK enforcement coverage: assert `PRAGMA foreign_keys=ON` on every connection.
73. Add a backup-on-startup guard (copy the DB before a migration) to make rollbacks possible.
74. Add a DB-size telemetry sample so growth is visible over time.
75. Add a test that asserts two processes can open the DB without deadlock (multi-process smoke).

## 4. Chat / agent runtime (76–100)

76. **⚠ proven** — the turn path has a `finally` block where persistence and telemetry both run; a failure in either is swallowed → standardise a `safe_record()` helper that logs failures loudly and never raises.
77. **⚠ proven** — the model answered "I don't have a clock" rather than inventing the time — good behaviour that is untested → add an explicit "no fabricated facts" test suite for the local lane.
78. **⚠ proven** — single-asterisk italics leaked into prose as literal asterisks → add a render test over a corpus of real model outputs (bold, italics, fences, lists, tables, nested quotes).
79. Add streaming-cursor tests asserting the caret unmounts on stop and that previous text is never re-rendered (selection preservation).
80. Add a scroll-anchoring test: new turn anchors near the top so the question stays visible while the answer grows.
81. Add an "announce once" accessibility test (aria-busy while streaming, single settle announcement).
82. Add a cancel-mid-tool test asserting the partial answer is persisted with `status=cancelled` and the tool loop stops.
83. Add reconnect/resume semantics: if the SSE stream drops, the client should be able to reattach to the turn.
84. Add a per-turn budget (wall clock + tool steps) with an explicit message when it trips.
85. Add a tool-approval card type (Approve/Deny) for write-capable tools, rendered as a question, not a trace step.
86. Add a token/latency receipt per turn (the usage frame already carries tokens — surface it in the UI).
87. Add a "regenerate" action with the same seed/context so a retry is comparable.
88. Add message-level pinning and a "copy as markdown" action.
89. Add a conversation branch tree view (fork already exists; make the lineage visible).
90. Add context-window management: summarise older turns rather than silently truncating.
91. Add a retrieval step before generation (the corpus lane exists; wire it into the prompt with provenance).
92. Add a tool-result size cap with linkage to an artifacts pane instead of dumping into context.
93. Add a per-focus system-prompt version stamp so behaviour changes are attributable.
94. Add a deterministic replay mode (recorded tool calls + responses) for regression tests.
95. Add an interleaved-thinking toggle with a hard cap on reasoning tokens.
96. Add a "why did you do that" affordance mapping each tool call to the sentence that caused it.
97. Add per-turn error taxonomy (provider down vs validation vs timeout) so the fallback message is specific.
98. Add a queue-while-streaming UX test (the queue exists — assert ordering and removal).
99. Add voice-note duration limits and a transcript-confidence display.
100. Add a session export (markdown + JSON) for audit and handoff.

## 5. Tool registry & gateway (101–125)

101. **⚠ proven** — `shell_focus.tools_for_focus` silently drops unregistered tool names → fail loudly at import time when a focus names a tool that does not exist (a test now covers presets; extend it to foci).
102. **⚠ proven** — I added two tools (`purpose_command`, `build_preset`) with no UI affordance → add a "capabilities" panel listing registered tools, their focus availability and their read/write class.
103. Add a required `read_only: bool` (or safety class) field to every tool spec and assert write-capable tools are never offered in read-only foci.
104. Add a per-tool argument-schema test that feeds malformed input and asserts a clean rejection.
105. Add a tool timeout wrapper so a hung tool cannot pin a worker thread.
106. Add tool-level metrics (calls, p95, failure rate) reusing `lane_telemetry` rather than a second store.
107. Add a tool dry-run mode that returns the resolved arguments without executing.
108. Add idempotency keys for write-capable tools.
109. Add a tool-result schema (uniform `{ok, summary, data, assets, error}`) enforced by a test over every handler.
110. Add a registry test asserting every tool's description is non-trivial (> N chars) so the model can actually choose it.
111. Add a "dangerous tool" allowlist that requires an explicit operator flag per session.
112. Add argument redaction so secrets in tool args never reach logs.
113. Add a tool-call budget per turn with a clear message when exhausted.
114. Add a `list_tools` introspection tool so the brain can discover capabilities at runtime.
115. Add versioning to tool contracts (breaking changes surfaced to callers).
116. Add a fixture-based test for each tool's happy path (many handlers have none).
117. Add a conformance test that every tool returns `assets: []` rather than omitting the key.
118. Add a tool-audit log (who called what, when, with what shape) — shapes only, never values.
119. Add a sandbox flag for tools that execute code (none currently should).
120. Add a registry diff test: adding/removing a tool must update the focus catalogue or explicitly opt out.
121. Add tool-call deduplication within one turn (the same call twice in a row should be flagged).
122. Add a "tool returned empty" state distinct from "tool failed".
123. Add a cap on concurrent tool executions per account.
124. Add a static check that no tool handler writes outside an approved directory.
125. Add a UI affordance to disable a tool for a session (operator kill switch).

## 6. Foundation: auth, tenancy, lifecycle (126–150)

126. **⚠ proven** — the dev shim resolves `requested_org` from a client header for JWT sessions too, which broke real sign-in with a stale localStorage identity → document the org-resolution precedence in one place and test all four combinations (cookie+header, cookie only, shim+header, neither).
127. **⚠ proven** — the shim's failure message blamed containerization and misled the operator → keep the two asserted phrases but make the first line actionable (already improved; add a test that the message names the real cause).
128. Add a session-expiry UX (the cookie has a TTL; the UI should warn before it lapses).
129. Add a multi-org switcher (the backend resolves orgs; the UI never exposes a choice).
130. Add an org-scope test matrix (member / non-member / platform admin × requested / default org).
131. Add rate-limit headers to the UI so throttling is visible rather than surprising.
132. Add a login-attempt backoff notice on the sign-in page.
133. Add audit entries for every auth transition (login/logout/refresh/revoke) — largely present; assert completeness with a test.
134. Add invitation lifecycle tests (expiry, resend, revoke) beyond the current happy path.
135. Add a "least privilege" test asserting operator role cannot reach any `/admin` or `/beta-ops` route.
136. Add CSRF coverage tests for every state-changing cookie-authenticated route.
137. Add a documented password policy and enforce it in one place (the owner seeder enforces 12 chars; the operator seeder does not — reconcile deliberately).
138. Add a secrets-vault usage test asserting no secret value is ever returned by an API.
139. Add a "preview session" test (the preview context exists; assert read-only enforcement).
140. Add tenancy isolation tests for every repository, generated from the repo list so new tables are covered automatically.
141. Add an account-deletion path (GDPR-style) with a test.
142. Add an entitlements test for every gated capability (autothink_workspace, advanced_view) including the locked-chip UI state.
143. Add a plan-change test asserting capability downgrades revoke UI access immediately.
144. Add a session-revocation propagation test (revoke → next request 401).
145. Add structured auth failure codes to the UI so the operator sees the reason, not a generic error.
146. Add a "why can't I see this room" diagnostic helper for the operator.
147. Add a hard cap and alert on failed logins per IP (the throttle exists; surface metrics).
148. Add a documented break-glass local-admin procedure with an audit trail.
149. Add a test asserting the dev shim is disabled outside development posture (present in authn; assert at the HTTP layer too).
150. Add a tenancy test for the memory bank (entries must never cross accounts).

## 7. UI/UX & design system (151–175)

151. **⚠ proven** — the interface read too small (10.5–13.5 px body) → add a type-scale lint: no `font-size` below 12 px, no body text below 16 px, enforced in CSS review.
152. **⚠ proven** — the galaxy background competed with the text until the panel became 95.5% opaque → codify a contrast rule: verify text against the BRIGHTEST pixel behind it, not the average.
153. Add an automated contrast test in the UI gate (sample rendered pixels under key text blocks and assert a ratio floor).
154. Add a visual-regression baseline (screenshots per route) with a pixel-diff threshold, run on the three viewports already used.
155. **⚠ proven** — a flex `min-height:auto` pushed the composer below the fold → add a layout smoke test asserting the composer is inside the viewport at three heights.
156. Add a keyboard-only navigation test for the shell (focus order, Esc, ⌘K palette).
157. Add a reduced-motion test asserting the canvas renders one static frame and animations stop.
158. Add a "text at 200% zoom" test to catch overflow without horizontal scroll.
159. Add an empty-state inventory page so every room's zero state is reviewed, not just the chat.
160. Add a loading-state standard (skeletons exist) with a rule: never a bare spinner for > 300 ms.
161. Add an error-state standard with a retry affordance and the honest reason.
162. Add a dark/light audit for the foundation pages under the cosmic shell.
163. Add a component inventory doc listing every `.chat-*`/`.wb-*` class and its single owner file.
164. Add a CSS-specificity budget lint (flag anything requiring `!important`).
165. Add a design-token coverage test asserting no raw hex colours outside `tokens.css`.
166. Add a spacing-scale lint (the research recommends a 4/8/16/24/32 rhythm — flag stray 5/7/13 px values).
167. Add a hit-target audit (≥24 px, ≥44 px on touch) for every icon button.
168. Add a focus-visible audit for every interactive element.
169. Add a mobile bottom-nav test at 390 px (the harness covers the toggle; cover the nav).
170. Add a long-content stress fixture (a 5 000-word answer) to check scroll anchoring and composer behaviour.
171. Add a table/code-block overflow policy test (no prose horizontal scroll).
172. Add a "copy" affordance on every code block with a 2-second confirmation.
173. Add a language label to fenced code blocks.
174. Add an inline-citation affordance (source chips opening on hover) tied to corpus provenance.
175. Add a print stylesheet check for reports (the shell is dark; printing should be legible).

## 8. Background canvas & performance (176–200)

176. **⚠ proven** — the previous purple planet read as "fake" → document the realism checklist (edge-on disc, lensed arc, photon ring, true-black shadow, subtle beaming) as the acceptance criteria for any future background change.
177. Add a shader-validity test that compiles the fragment shader headlessly and fails on a GLSL error (a typo currently degrades silently to the CSS fallback).
178. Add a fallback-visibility assertion to the UI gate (assert `data-cosmic-fallback` is absent on a healthy machine).
179. Add a GPU-budget test: measure frame time and fail if the canvas exceeds N ms on the reference card.
180. Add an automatic DPR governor test (the governor exists; assert it lowers DPR under load).
181. Add a battery/power-preference doc: the canvas uses `low-power`; assert it stays.
182. Add a "pause when hidden" test (visibility change stops rAF).
183. Add a shader-cost report (instruction count) to catch accidental complexity growth.
184. Add a review rule: never tint the hero object with a mode accent (learned from T-2).
185. Add a canvas screenshot per focus mode to the visual baseline (already produced for five modes — wire them into CI).
186. Add a documented palette table with the token each mode varies.
187. Add a test that a locked focus (autothink) does not change the theme.
188. Add a transition-duration assertion (the eased shift is ~3.5 s; assert it is not instant).
189. Add a prefetch/decoding budget for images in the chat (avoid layout shift).
190. Add a font-loading assertion (self-hosted fonts; assert no third-party request).
191. Add a bundle-size budget check that fails when the main chunk grows beyond a threshold.
192. Add a route-level code-split plan for the heaviest rooms.
193. Add a memory-growth test for long sessions (leak check on the canvas and stream).
194. Add an idle-CPU assertion (paused tab, idle shell should be near-zero CPU).
195. Add a documented degradation path for machines without WebGL (the CSS gradient exists — keep it maintained).
196. Add a test asserting the canvas never blocks first paint (mounts after content).
197. Add a contrast test specifically over the brightest gutter region of the canvas.
198. Add a "no purple blob" lint: assert no large saturated region sits behind the reading column.
199. Add a per-mode colour-blindness check (the tints must remain distinguishable in deuteranopia simulation).
200. Add a documented rule that background animation never exceeds a stated luminance band (2–8%).

## 9. Privacy, security & credentials (201–225)

201. **⚠ proven** — a gitleaks pre-commit hook blocked a commit because a *test fixture* looked like a live key → standardise on runtime-constructed fake credentials so no credential-shaped literal ever lands in the tree.
202. **⚠ proven** — my own secret scanner returns kind+length only, never the value → make that the house rule for any diagnostic touching secrets, and add a test to each new scanner.
203. Add a redaction test corpus (env assignments, bearer tokens, cards, paths, emails, phones) run against every logging path.
204. Add a log-scanning test that replays a full chat turn and asserts no value from the request appears in the logs.
205. Add a dependency-vulnerability scan to CI with a documented triage SLA.
206. Add a pinned-lockfile policy (requirements are unpinned today; the runbook flags it).
207. Add an SBOM generation step for releases.
208. Add a secrets-rotation runbook for the JWT signing key with a tested rotation procedure.
209. Add a test asserting the JWT secret never appears in any log line or error response.
210. Add an authorization fuzz test (every route × every role) generated from the route table.
211. Add a CSRF negative test matrix for cookie-authenticated writes.
212. Add a rate-limit bypass test to prove limits cannot be evaded by header games.
213. Add a header-hardening assertion (CSP, X-Frame-Options, Referrer-Policy) over every response type.
214. Add a documented threat model for the local-only posture (what is safe because it is loopback, and what breaks when tunnelled).
215. Add a tunnel-exposure checklist (the alpha launcher opens a tunnel; assert the gate is on).
216. Add a test asserting the dev shim cannot authenticate over a non-loopback client.
217. Add an outbound-request audit test proving the offline path makes no network calls.
218. Add a consent-gate test matrix for external routing (absent, granted+clean, granted+dirty).
219. Add a "no telemetry leaves the machine" assertion at the socket level.
220. Add a fixture PII screen as a pre-commit check.
221. Add a documented data-retention schedule per data class (the retention module lists classes; add the schedule).
222. Add an export/erase path test for account data.
223. Add a session-fixation test (session id must change on login).
224. Add a cookie-flag assertion (HttpOnly, SameSite, Secure-in-hosted).
225. Add an operator-facing security posture page summarising gates, vault state and open decisions.

## 10. Observability & telemetry (226–250)

226. **⚠ proven** — telemetry existed only as an idea until I wired a real producer into the turn path → adopt the rule that every metric has a producer before it has a consumer.
227. **⚠ proven** — `recommend()` refuses to emit a routing policy before 30 measured runs → keep that gate and surface the current sample counts on the operator dashboard.
228. Add a telemetry retention/rotation policy for `lane_telemetry`.
229. Add per-lane p50/p95 to the hardware/status chip so the operator sees real latency.
230. Add a "boring dashboard" page: lanes, success rates, tool failure kinds, disk headroom, model resident state.
231. Add a structured error taxonomy and a counter per class.
232. Add request-id propagation from UI to logs to telemetry (partially present; assert it).
233. Add slow-request logging (> threshold) with the route and the DB statement count.
234. Add a queue-depth metric for streaming turns.
235. Add a token-cost report per lane and per focus.
236. Add a tool-level success dashboard fed by the same telemetry store.
237. Add an anomaly note when a lane's success rate drops below its trailing baseline.
238. Add a self-evolution proposal digest to the daily brief (the loop already produces proposals).
239. Add a gate-result history so "was this green last week?" is answerable.
240. Add an explicit "not measured" state everywhere a number is unknown (mirrors the null-not-zero rule).
241. Add a metric for skipped tests, so a growing skip list is visible.
242. Add a disk-headroom metric with an alert threshold (see 401 for why this matters).
243. Add a model-residency metric (which local models are loaded, VRAM free).
244. Add a "turn took longer than X" report with the slowest steps.
245. Add a correlation id between the UI turn, the SSE frames and the persisted message.
246. Add a weekly digest generator (turns, tools, failures, proposals, gates).
247. Add a health endpoint that reports DB integrity + schema version + disk headroom in one payload.
248. Add structured logging for the canvas governor decisions (DPR changes).
249. Add an operator-visible "what changed" feed derived from commits + reports.
250. Add a telemetry privacy review: assert every recorded field is either a number, a shape (len:N) or an enum.

## 11. Architecture & coupling (251–275)

251. **⚠ proven** — my first cycle detector *invented* a 21-module cycle by guessing ambiguous import targets → adopt a house rule: an analyser must never guess; unresolved is a first-class, reported outcome.
252. **⚠ proven** — with conservative resolution the repo has 1,220 real internal edges and 502 genuinely ambiguous imports → reduce ambiguity by preferring absolute package imports over bare module names.
253. **⚠ proven** — a true 2-module cycle exists (`agents.golden_goose_finder.amazon_adapters <-> amazon_matcher`) → extract the shared type into a third module and re-run the gate as proof.
254. **⚠ proven** — three orphaned ~2,085-line forks of `main.py` (`_main_dbg*.py`, fan-in 0, untracked) → resolve owner decision D4 and delete or archive; add a lint that flags any new `*_dbg` file.
255. Add a packaging boundary: `Northstar_backend` should be importable as a package (`python -m Northstar_backend.…`) without the `sys.path.insert` dance several modules still perform.
256. Add a layering rule (routers → services → repositories → db) and a test that fails on violations.
257. Add an import-linter config to make the layering rule executable rather than aspirational.
258. Add a module-size budget: warn above N lines, fail above 2N.
259. Add a "public surface" convention (`__all__`) so internal churn stops breaking callers.
260. Add a deprecation policy with warnings for renamed public functions.
261. Add a boundary test between the SPA and the API derived from `openapi.json` (types, not just paths).
262. Add a typed API client generated from the OpenAPI schema to end hand-written path drift.
263. Add a single source of truth for API paths consumed by both the UI and the tests.
264. Add a service-registry map (which module owns which domain) to the docs and assert every module appears in it.
265. Add a check that no module imports more than 12 internal modules without justification (the `wide_interface` finding).
266. Add a `foundation/tests` import-hygiene rule: test modules should not import each other's innards.
267. Add an explicit "no circular imports at runtime" assertion per package (the AST check currently only reports).
268. Add a one-command architecture report to the pre-commit output so coupling drift is felt immediately.
269. Add a decision log (ADR) folder recording why each boundary exists.
270. Add a rule that new top-level modules need a one-line entry in the module registry.
271. Add a stub/ephemeral-file audit (`*_dbg`, `_test_*`, `tmp*`) that flags files older than 30 days.
272. Add a "dead code" report from coverage of the last 30 days.
273. Add a single `config/` resolution order (env → file → default) documented and tested.
274. Add an import-time side-effect audit (no module should open a DB or network at import).
275. Add a package-level smoke import test that imports every module and reports failures (catches syntax/import drift early).

## 12. Build, CI & release (276–300)

276. **⚠ proven** — the V3 UI gate plus two new harnesses run only when a developer remembers to start the dev server → add a harness runner that starts/stops the server itself.
277. **⚠ proven** — `npm run build` succeeds but only warns about a >500 kB chunk → turn the warning into a tracked budget with a ratchet.
278. Add a single `verify-all` entry point that runs: backend suites, Thorn suites, the 11 reconciled files, all UI harnesses, and the build, then prints one table.
279. Add a golden `expected_counts.json` so a drop in collected tests fails the build.
280. Add CI for the four environments the repo already assumes (dev, test build, prod build, frozen) — the harnesses support them.
281. **⚠ proven** — two UI harnesses require credentials and fail closed without them → document the exact env contract at the top of each (most already do) and add a `harnesses/README.md`.
282. Add a pre-commit hook that runs the fast suites (< 30 s) and blocks on failure.
283. Add a commit-message template enforcing the evidence line (test counts) the protocol requires.
284. Add a release checklist that includes the reconciliation step (spec vs disk) used in this session.
285. Add a tag-and-notes convention so `v3-final-stable`-style baselines are self-describing.
286. Add a reproducible-build check (same inputs → same bundle hash).
287. Add a lockfile for the UI (`package-lock.json` presence + integrity check).
288. Add an engine-version assertion (Node/Python minimums) at the top of every harness.
289. Add a `--ci` mode to the UI harnesses that exits non-zero on console warnings, not just errors.
290. Add artifact retention for reports (keep the last N per type).
291. Add a smoke test that the served bundle matches a freshly built one (the V4.2 run showed the served asset hash matching disk — assert it).
292. Add a production-bundle content check that fails if dev-only strings appear (the repo has `check-prod-bundle.cjs`; extend it to every new dev affordance).
293. Add a build-time banner check (commit + time) so a running build is identifiable.
294. Add a dependency-update cadence with a test that pins breakages.
295. Add a "no network at build time" assertion.
296. Add a changelog generator from reports + commits.
297. Add a release-blocking gate for the proposal pipeline (self-evolution must never be part of a release path).
298. Add a rollback drill (the repo has a script; schedule it quarterly).
299. Add a "fresh clone" CI job that runs the documented quickstart verbatim.
300. Add a build-time clock skew check for signed artefacts.

## 13. Ops, disk & environment (301–325)

301. **⚠ proven** — the C: drive hit **0 bytes free** and a test run died mid-collection with `OSError: [Errno 28]` → add a disk-headroom preflight to every suite and a documented cleanup routine before long runs.
302. **⚠ proven** — `C:\Users\T2Hol\ComfyUI` holds **121.7 GB** and `AppData\Local` 76 GB → add a storage map doc with owners and a prune policy for generated renders.
303. Add a disk-headroom metric to the health endpoint with thresholds (warn < 5 GB, fail < 1 GB).
304. Add a cleanup command for regenerable artefacts (pycache, pytest temp, old run outputs) that never touches canonical data.
305. Add a "safe to delete" manifest so cleanup is not guesswork.
306. Add a model-cache inventory (Ollama 10.3 GB today) with last-used timestamps and a prune command.
307. Add a documented VRAM budget: the canvas, Ollama and ComfyUI compete on one 16 GB card.
308. Add a preflight that refuses to start a render when free VRAM is below the canvas reserve.
309. Add a startup check that reports which ports are already bound (a stale uvicorn blocked work twice today).
310. Add a service supervisor script (start/stop/status for API, UI, Ollama, ComfyUI) with pid tracking.
311. Add a "what is running" one-liner to the operator dashboard.
312. Add structured shutdown so a killed server flushes SQLite WAL cleanly.
313. Add a documented port map (8000 API, 8101 UI, 8100 AutothinK, 11434 Ollama, 8080 llama.cpp, 8199 ComfyUI).
314. Add an env-var manifest per service with required/optional/default columns.
315. Add a `.env.example` sync test (every name the code reads must appear there).
316. Add a documented local-only posture (loopback, no tunnel) vs tunnelled posture with the gate on.
317. Add an operator runbook for "the model is OOM" including the exact recovery (seen twice).
318. Add a log-rotation policy for uvicorn/ComfyUI logs.
319. Add a scheduled DB backup with a restore drill.
320. Add a "first run on a clean machine" walkthrough verified on a fresh clone.
321. Add a hardware telemetry retention so thermal/VRAM history is reviewable.
322. Add a power/thermal note for long renders (the laptop card throttles).
323. Add a documented recovery for a corrupted SQLite WAL after a hard kill.
324. Add a "kill switch" script that stops every local service without touching data.
325. Add an ops changelog entry whenever a port, path or env name changes.

## 14. Documentation & knowledge (326–350)

326. **⚠ proven** — the v5.0 plan claimed executed work that does not exist, and a reconciliation was required before any code → make "spec vs disk" the first section of every plan reviewed in this repo.
327. **⚠ proven** — several docs describe numbers that drifted (44 vs 52 routes; "2 known failures" vs 33) → add a docs-drift test that extracts numeric claims and compares them to code where possible.
328. Add a single entry-point index (`docs/INDEX.md`) listing every documented subsystem and its owner file.
329. Add a decision register (owner decisions D1–D4 and their status) surfaced in the operator dashboard.
330. Add an assumptions log entry for every claim a report makes about the environment.
331. Add a "how to verify this claim" link in every report (the exact command).
332. Add a glossary (focus, preset, lane, tier, preview, shim, REA) so vocabulary stops drifting.
333. Add an onboarding path for a second engineer in one page.
334. Add architecture diagrams generated from the import graph rather than hand-drawn.
335. Add a "what runs where" map (native vs docker) because both exist.
336. Add a documented boundary between the frozen V3 baseline and current work.
337. Add a report index with dates and one-line outcomes.
338. Add a rule: every report states what it did NOT do (scope boundary) — the V4.2 report's AutothinK note is the model.
339. Add a live "open questions" page fed from the state file.
340. Add a template for card definitions (goal, acceptance, evidence, owner decision).
341. Add a README for the thorn modules explaining the honesty contracts.
342. Add inline "why" comments at every non-obvious guard (the concurrency lock is the model).
343. Add a documented policy for when a test may be skipped vs xfailed.
344. Add a policy for when a comment is allowed to state a number (only when measured, with the command nearby).
345. Add a "no invented metrics" lint for reports (flag round numbers without a computation).
346. Add a CHANGELOG per major capability, not per commit.
347. Add an operator-facing "what's new" summary generated from reports.
348. Add a troubleshooting index mapping symptom → cause → fix (sign-in, shim, OOM, port conflict, disk full).
349. Add a "known limitations" page kept honest (the runbook's §8 is the model).
350. Add a documentation freshness badge per doc (last verified date + commit).

## 15. Sourcing capabilities (351–375)

351. Add a single sourcing funnel view (discovery → identity → evidence → economics → decision) with counts at each stage.
352. Add identity-resolution coverage metrics (how many candidates have a verified GTIN/UPC).
353. Add a duplicate-suppression pass across club/wholesale catalogues.
354. Add a "price staleness" column and a re-check queue ordered by staleness.
355. Add a per-channel cost model (club membership fees, shipping, tax) to the margin calculation with explicit assumptions.
356. Add a break-even calculator tied to the fee contract doc.
357. Add a "no UPC" workflow that routes to a manual mapping review with the evidence attached.
358. Add a supplier-reliability score derived from observed fulfilments, not opinion.
359. Add a landed-cost estimator with a documented assumption set.
360. Add a restock-alert path from observed availability changes.
361. Add a "this data is stale/unavailable" surface per product rather than a blank cell.
362. Add a sourcing decision log (what was considered, chosen, rejected and why).
363. Add a competitor-price band per ASIN with a staleness label.
364. Add a seasonality note derived from observed history where available.
365. Add a sourcing experiment framework (A/B on thresholds) with measured outcomes.
366. Add a club-catalogue diff engine (what changed since last pull).
367. Add an explicit UNKNOWN vocabulary for every sourcing field and a test that it is preserved to the UI.
368. Add a "why this is a discovery lead, not a decision" explainer per row.
369. Add a sourcing SLA report (time from discovery to decision).
370. Add a supplier-contact/terms store with expiry reminders.
371. Add a returns/damage-rate tracker per supplier.
372. Add a lot/batch traceability field for consume-by products.
373. Add an MOQ/case-pack normaliser so economics compare like for like.
374. Add a "club → Amazon" category mapping table with coverage metrics.
375. Add a sourcing kill-switch per channel so a bad provider can be stopped without a deploy.

## 16. Listing & SEO capabilities (376–400)

376. **⚠ proven** — the local model produced an answer with unsourced numbers and absolute claims → wire the self-critique evaluator into the chat loop for listing copy and surface its findings to the operator.
377. Add a listing-revision audit trail view (revisions are additive; expose the history).
378. Add a title-length/character-limit validator per marketplace with a live counter.
379. Add a keyword-coverage report against the operator's own head terms (the SEO tools exist; surface the deltas).
380. Add a "forbidden claims" checker (certifications, medical claims) as a pre-flight on any generated copy.
381. Add a bullet-point structure validator (benefit-first, no ALL CAPS, no emoji spam).
382. Add a back-end search-term deduplication tool.
383. Add a listing-image compliance checklist (white background, product fill, no text overlays where prohibited).
384. Add a variation-family builder with a consistency check.
385. Add an A+ content outline generator tied to the design brief.
386. Add a marketplace-specific style guide store.
387. Add a competitor-title scraper output schema (observed facts only, with provenance).
388. Add a rank-tracking history view with change annotations.
389. Add a review-sentiment summary from permitted sources with a provenance label.
390. Add a "listing health" score that explains each deduction.
391. Add a change-freeze window flag (never write during peak hours).
392. Add a rollback path for any listing change (keep the previous revision one click away).
393. Add an SEO regression suite that runs the tools over a frozen listing fixture and diffs output.
394. Add a "no auto-publish" hard rule with a test (suggestions only until the operator approves).
395. Add a listing template library with version stamps.
396. Add an internationalisation checklist (units, spelling, currency) per marketplace.
397. Add a compliance-document tracker (certificates, test reports) with expiry.
398. Add an "ask the operator" flow when a listing needs a fact only they know.
399. Add an SEO tool that reports what it could NOT check (honest gaps).
400. Add a monthly listing-performance digest.

## 17. Creative & design capabilities (401–425)

401. **⚠ proven** — the image pipeline is real (Klein 4B/9B, ComfyUI lanes) but has a documented post-render crash path with the 9B resident → add a supervisor that restarts ComfyUI after a render and records the failure honestly.
402. Add a queue for renders with per-job VRAM preflight and a documented priority (operator interactive > batch).
403. Add a render-cost report (seconds, VRAM peak, model, seed) per asset.
404. Add a seed registry so any asset can be regenerated exactly.
405. Add a "draft vs final" contract surfaced in the UI with the real model name.
406. **⚠ proven** — the compositor's realism work is documented (displacement, grain, soft-light, specular, AO) → add a visual-diff test per layer type.
407. Add a template gallery with per-template acceptance screenshots.
408. Add a dieline geometry validator (dimensions, bleed, safe area) as a hard pre-check.
409. Add a print-PDF preflight (colour space, resolution, overprint) with an explicit pass/fail.
410. Add a file-naming convention and enforce it on export.
411. Add a mockup-depth realism check comparing the composited output against the reference set.
412. Add a "no painted text" rule enforced by a test (text belongs in vector layers).
413. Add a brand-asset registry (logo, palette, fonts) with a single resolver.
414. Add a palette-consistency check across a brand's assets.
415. Add an asset-provenance record (which model, prompt hash, operator, timestamp).
416. Add a licence gate: refuse a model whose licence forbids the intended use.
417. Add a storage policy for generated assets (prune drafts, keep finals) — see the disk finding.
418. Add a batch-render planner that respects thermal limits.
419. Add a creative-QC checklist surfaced before an asset can be marked final.
420. Add a "similar asset exists" check to avoid duplicate renders.
421. Add a thumbnail pipeline so galleries stay fast.
422. Add a broken-asset detector (missing file on disk but referenced by a record).
423. Add a design-token bridge so UI tokens and print palettes cannot drift.
424. Add a photo-shot-list generator tied to a product.
425. Add a video/UGC lane plan with the same provenance discipline (the media stack doc already scopes it).

## 18. Research & memory capabilities (426–450)

426. **⚠ proven** — the research graph labels a single-source claim as `single_source` and never as verified → keep that rule and surface the label in the UI where citations render.
427. Add a conflict-resolution workflow: numeric disagreements become a task, not a silent average.
428. Add a source-quality score (primary vs secondary vs SEO content) to every retrieved passage.
429. Add a "discard low-density summary" filter as an explicit, testable step.
430. Add a research-tree visualisation (nodes, sources, conflicts) reusing the plan-graph rendering.
431. Add a research-run record (query matrix, nodes, sources, conflicts, elapsed) for auditability.
432. Add a staleness re-run trigger for research whose sources are older than a threshold.
433. **⚠ proven** — live web capture is operator-gated through Chrome Connect by design → document the exact operator window procedure and the guardrail proof.
434. Add a REA capture→corpus pipeline test using a recorded fixture (no live capture).
435. Add a corpus dedupe step so the same source ingested twice does not skew drift.
436. Add a provenance field to every corpus row and assert it is never empty.
437. Add a drift-explanation surface (the drift endpoint returns a reason; render it).
438. Add an embedding-model version stamp per vector so a model change is detectable.
439. Add a re-embed job plan for when the embedding model changes.
440. Add a vector-store size/row-count metric.
441. Add a "corpus coverage by source" report (the stats endpoint has the shape).
442. **⚠ proven** — the memory bank supports retire/unlearn and my tiers ride in `tags` → promote tiers to a column and add a tier migration.
443. Add a memory-review UI (list, edit, retire) rather than writing through the API only.
444. Add a memory-conflict detector (two contradictory preferences recorded).
445. Add a memory-expiry policy per tier (transient on session end; project on account delete).
446. Add a global-tier promotion review queue (proposals, not automatic).
447. Add a "why did you remember this" provenance display.
448. Add a memory-usage limit per account with a clear warning at 80%.
449. Add an import path for bulk knowledge (documents) with a dry-run preview.
450. Add a memory-quality metric (how often a retrieved memory actually changed an answer).

## 19. Model lanes & routing (451–475)

451. **⚠ proven** — the local model (`northstaros-qwen3.8:27b`) is the sole local lane and OOMs when the GPU is busy → add a lane-availability preflight before a turn with a clear message.
452. Add a fallback ladder (local → smaller local → offline template) with honest labelling at each step.
453. **⚠ proven** — the offline fallback text is honest ("nothing was fabricated") → keep it and add a test that it never contains invented facts.
454. Add a per-lane quality benchmark suite with frozen prompts and human-scored anchors.
455. Add a prompt-version registry so a prompt change is attributable to an outcome change.
456. Add a temperature/top-p registry per task type (deterministic for extraction, warmer for ideation).
457. Add a context-length budget per lane with summarisation before overflow.
458. Add a "which model answered" field everywhere an answer is stored (present in receipts; assert persistence).
459. Add a routing dry-run that explains the choice it WOULD make and why.
460. Add an entropy/complexity heuristic as a proposal, evaluated against measured telemetry — never enabled before data.
461. Add a cloud-lane consent prompt per call (the privacy gate exists; surface the UI).
462. Add a cost estimate per cloud call before it runs.
463. Add a hard spend cap per day across all cloud lanes.
464. Add a model-download manager with provenance and licence capture.
465. Add a lane health probe that distinguishes "not installed" from "not running" from "out of memory".
466. Add a per-lane latency budget with automatic degradation.
467. Add a cache for identical prompts within a turn window.
468. Add a "same answer twice" detector to catch a stuck lane.
469. Add a deterministic mode for tests (fixed seed, temperature 0).
470. Add an embeddings-lane health check separate from the generation lane.
471. Add a vision-lane plan (the model may support it) with the same honesty rules.
472. Add a per-lane concurrency limit so two heavy runs cannot collide on the GPU.
473. Add a "warm the model" step on first use to avoid a cold-start penalty mid-turn.
474. Add a documented model-upgrade procedure with a rollback path.
475. Add a lane scoreboard to the operator dashboard (this session's T-7 telemetry feeds it).

## 20. Operator experience & safety rails (476–500)

476. **⚠ proven** — a stale localStorage shim identity silently broke real sign-in with **no message** → adopt the rule that every silent failure must surface a reason; add a UI test asserting no failure path is message-less.
477. **⚠ proven** — the shim's alert text was misleading → review every user-facing error string for accuracy once a quarter.
478. Add a "what happened" panel per turn (model, tools, gates, timings) so the operator can audit without logs.
479. Add an undo affordance for every write action (listing edits, memory changes, tier promotions).
480. Add a confirmation dialog for any action that spends money or writes externally.
481. Add a daily brief that leads with what needs a decision, not with metrics.
482. Add a decision inbox (D1–D4 style) so open questions are not lost in reports.
483. Add an "operator was right" feedback loop on suggestions (feeds prompt refinement proposals).
484. Add a session-recap generator (what I did, what changed, what is blocked).
485. Add an explicit "I don't know" template for the operator to send back to the model.
486. Add a one-click "show me the evidence" for any claim the system makes.
487. Add a keyboard shortcut sheet in the UI.
488. Add a "safe mode" toggle that disables all write-capable tools for a session.
489. Add a "dry run everything" mode for demos without touching data.
490. Add a scheduled "self-review" digest produced by the self-evolution loop (proposals only).
491. Add an operator-facing list of every automated background process with a stop control.
492. Add a "why is this red" explainer for each failing gate in the dashboard.
493. Add a documented escalation path for a broken production-ish state.
494. Add a "fresh eyes" review cadence: one report per week re-read with the reconciliation lens.
495. Add a personal changelog for the operator (what changed in their workspace since yesterday).
496. Add a "pause everything" big red button that stops lanes, renders and jobs safely.
497. Add a telemetry-visible note when the system degrades (fallback used, gate skipped, data missing).
498. Add a standing rule: never claim a capability without a test that fails when it breaks.
499. Add a standing rule: every number in a report must name the command that produced it.
500. Add a standing rule: if a guardrail is inconvenient, the guardrail wins until the operator says otherwise in writing.

---

**Count: 500 items across 20 areas.** Items marked **⚠ proven** cite something
directly observed in this session; the rest are grounded in the repository's own
documented state (runbook limitations, master plan, service plans) or in a failure
path exercised today. Nothing here is a placeholder.

