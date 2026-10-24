# Scan: Herk Edit Kit + AgentConnect (2026-10-24)

Two operator-supplied candidates. Verdicts recorded in `shared/provider-suite.json`
(`agentconnect`, `herk_edit_kit`) so the lane check carries the reasoning forward.
Nothing was installed; no network calls made to either project.

## Verdict table

| Repo | Verdict | One-line reason |
|---|---|---|
| `agentconnect-md/agentconnect` (1.5k★, Apache-2.0) | **Rejected** | A second harness with team-scale infrastructure; duplicates the Master Brain |
| `nateherkai/herk-edit-kit` (2.1k★, MIT + carve-outs) | **Parked** | Right shape, wrong job, and its render path collides with the Chrome Connect rule |

## 1. AgentConnect — rejected

What it is: an open-source platform where a fleet of agents (Claude Code, Codex, DeepSeek,
OpenCode, any ACP runtime) works alongside a team across Slack, Telegram, Discord, GitHub,
Linear, and webhooks. Self-hosted stack: Node monorepo (2,926 commits), Docker Compose with
PostgreSQL, Logto browser auth, optional TURN/STUN relay, Helm chart for Kubernetes.

Why it does not help Northstar:

1. **Second harness.** The platform decides where agents run, how sessions are placed, and
   which agent owns context. That is the Master Brain's role, and we refused OpenClaw on
   exactly these grounds. Running it would put a control plane between the operator and
   Northstar's own constitution.
2. **Team product for a one-operator bench.** Its value is shared visibility for teams
   (@-mention an agent in Slack, teammates take over sessions). Northstar has one operator
   and one working directory; there is no team to share with.
3. **Infrastructure cost with zero product value.** PostgreSQL + auth server + relay for a
   local FastAPI/React product is weight, not leverage.
4. **[Skills] overlap, not gap.** Per-agent memory, skills, and "reviewed Knowledge revisions"
   are features we already own as the skills plane + memory bank, with fail-closed loading.

**The useful nugget — Jev.** AgentConnect routes and gates agents with
[Jev](https://docs.typesafe.ai/introduction): reusable Decisions covering *when an agent
responds*, *routing a conversation to a specialist*, and *picking runtime + model per session*.
That is independent confirmation of the decision layer's design (`95dc8e30` → `b80ed1f`):
closed-label decisions, calibrated confidence, escalation instead of silent auto-answer.
If we ever add routing kinds to `decision_layer.py` (`respond_now`, `which_backend`),
Jev's taxonomy is the reference and laya stays the local free backend.

## 2. Herk Edit Kit — parked, with the four real reasons

What it is: 15 agentic video-editing skills for Codex/Claude Code, built on
[HyperFrames](https://github.com/heygen-com/hyperframes) (Apache-2.0) + GSAP. Transcript-driven
cuts, storytelling structure, 406 motion-graphics cards, style templates. The README shows
full reels edited end-to-end by an agent from raw footage.

Licences checked directly:
- `LICENSE` = **MIT** for the kit's own material, with an explicit carve-out: the AIS brand
  assets are *not* licensed for reuse and must be replaced.
- `THIRD_PARTY_NOTICES.md` = HyperFrames Apache-2.0; **GSAP keeps its own no-charge licence**;
  Google Fonts and example media stay with their owners.

Why not now, in order of weight:

1. **Browser-render collision.** HyperFrames renders motion graphics in a browser. Chrome
   Connect is the only sanctioned browser path and "no script may drive Playwright directly"
   is a §-level rule. Adopting the kit's render loop needs an explicit operator carve-out;
   none exists.
2. **Metered by default.** Transcript-driven cuts use ElevenLabs / OpenAI / Groq transcription
   (`.env.example`), and generated assets go through kie.ai — paid credits, which is a
   real-money approval gate every run.
3. **Mixed bundle rights.** The kit is clean for *our* internal use as a pattern, but GSAP's
   licence would have to be reviewed before anything customer-facing ships from that lane.
   The suite entry brands it `MIT` for the kit with the carve-outs recorded in notes.
4. **Job fit.** It edits *existing* talking-head footage. Northstar's UGC lane (ElevenLabs /
   Piper narration + FLUX.2 Klein stills, already in the suite) needs product-video
   **assembly** from stills and a script — an adjacent but different job. Zero of our current
   footage exists to edit.

**What is recyclable if the UGC/video lane becomes a priority:** the *shape* — skill files
with a fact contract + storytelling structure, and a numbered motion-cards library the agent
composes from rather than freestyles. That pattern ports to the Design Studio without
importing HyperFrames, GSAP, or any metered input.

## Cross-check against the standing rules

- No second browser path introduced (Chrome Connect untouched) ✅
- No scraping, no stealth tooling, no social-platform ingestion ✅
- Licence gates: both entries are `not_installed` on the local lane only ✅
- No paid-credit spend, no API keys fetched or stored ✅

## Companion commits

- `cf90e7ff` (earlier same session): 33-tool suite this update extends.
- This scan: 2 suite entries + this report. 24 `test_provider_suite` invariants re-run green.
