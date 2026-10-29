# Northstar OS — Product Overview

**Status:** narrative overview, 2026-10-29. Written to state what the product is and why the
default view is the default. Where this document and the running code disagree, §9 says so
explicitly rather than reinterpreting one into the other.

---

## 1. What Northstar OS is

Northstar OS is a commerce operating system for people who sell physical products. It is not a
dashboard bolted onto a spreadsheet and it is not a chatbot with a sidebar. It is one surface that
takes a plain-language request, decides what kind of work that request is, does the work with the
right specialist, shows its progress honestly, and hands back files you can use — with a record of
what changed and what it cost.

Under the single surface it holds the full operating loop of a product business:

| Stage | What the system does |
|---|---|
| **Find** | Product Finder and Golden Goose hunt sourcing opportunities; Competitor Monitor watches the field |
| **Judge** | Profitability, margin-safe budgets, and cost models decide whether an opportunity is real |
| **Build** | Design Studio produces packaging, dielines, listing imagery, A+ content, storefront and social assets |
| **List** | Listing Forge, Keyword Tracker and Listing Guardian write and defend the listing |
| **Move** | AdPilot, Social Pulse and Commerce Ops run demand and fulfilment |
| **Watch** | Monitoring, The Watch, Ledger and Rank Ledger keep the record straight |
| **Remember** | The Memory Bank stores facts, preferences and learned context per account and feeds them back into generation |
| **Build tooling** | AutothinK is the engineering workspace; small utilities (tip, percentage, break-even) are generated as self-contained pages on request |

Two things make it a system rather than a suite of pages. First, every specialist is reachable from
the same conversation, so a request does not have to be translated into a menu path. Second, every
action runs through one trust layer (§4), so "what the product can do" and "what it is allowed to do
right now" are never the same question answered in two different places.

## 2. The shape of it: one box, six focuses

The product surface is a conversation. You type; a router called **Bojo** decides whether to answer,
build, or hand off. Before it spends time or credits it says what it will do, which specialists it
will use, what it still needs from you, and roughly what it will cost. While it works you see real
progress per tool run, not a spinner. When it finishes you get a downloadable artefact and a change
log, plus how the result ties back to your keywords.

Around that box sit six focuses — **Auto, Create, Grow, Research, Operate, AutothinK** — which are
not separate apps but lenses on the same brain. A room route deep-links into the matching focus, so
an old bookmark lands in the right context instead of dumping you into a legacy page. AutothinK is
locked unless the account holds the `autothink_workspace` gate.

Live hardware telemetry (GPU utilisation, VRAM, temperature, RAM) sits in the shell chrome, because
generation is local and the operator deserves to see the machine's actual condition rather than a
guess.

## 3. What the interface refuses to fake

The design rule that shapes every screen: **nothing pretends**. An empty field shows a dash and says
what it needs. A missing provider shows a named boundary — expected engine, env var, gate flag —
instead of a placeholder image. A refused request says what it could have built. A render that dies
reports the real error, not a friendly one. The reason is not aesthetic: this product makes decisions
about money, and a cheerful fake is worse than an honest gap.

## 4. The trust layer

Northstar OS is built with two standing gates that always require a fresh, explicit operator
approval — (a) spending money or consuming paid credits, and (b) anything touching Amazon. Everything
else is autonomous by design; the product is meant to make its own outbound calls.

Around those gates:

- **Browser work goes through one controller.** Chrome Connect plans each step, evaluates the live
  page, stops at CAPTCHA, login, rate limits and consent, and journals every decision, tool call, URL
  and result. It runs headed, read-only by default, throttled, on a named leased profile. The host
  policy is a denylist; Amazon and its lookalikes stay in a hardcoded blocklist evaluated first.
  Nothing drives the browser by another route.
- **Two provider lanes, separately armed.** The local bench may use non-commercial weights and
  copyleft runtimes because nothing is resold. The cloud lane is restricted to commercially licensed
  tools. Each tool is checked against a registry before use, and a refusal is a refusal.
- **Gates never arm live actions by accident.** Plan entitlements control which *surfaces* you can
  see (`ui_gates`); they never unlock a live or paid action. That distinction is enforced in code,
  not in prose.

## 5. Why the conversation is the default view

The conversation is the default because it is the only view that is honest about what the system
actually is. Northstar is a routing brain with specialists behind it; a room-based shell presents
that as fifteen equal destinations and makes the user do the routing the brain was built to do. The
measured failure of the previous surface was exactly this: controls stacked three rows deep, a
narrow column with most of the panel empty, the composer — the one thing every request goes through
— as the smallest element on screen, artefacts reloading as unnamed "asset" tiles, and a permanent
error banner under the input.

So the default view is built as a real frame, not a page: one column that fills the viewport, only
the stream scrolls, prose capped at a readable measure while cards and artefacts use the whole
column, and the composer as the largest control on screen with a single row of options. Everything
heavy is one step behind the composer rather than in front of it.

The consequence that matters commercially: a first-time user can do real work in the first ninety
seconds without learning the product's internal taxonomy. That is the whole case for the default.

## 6. The Advanced view: power users, top tier only

The Advanced view is the dense room shell — the full inspector: layer geometry, guides, export
scale, raw prompt fields, per-room tool rails, and the specialist rooms as pages rather than focuses.
It is faster for someone who already knows where everything is and slower for someone who does not.
It is therefore not a preference toggle for the general population; it is a power-user surface.

Rules:

1. **Only the top tier can switch.** The ability is a backend-resolved capability, not a client
   setting: the shell context returns `advanced_view`, and the client degrades any advanced request
   to the default view when that capability is absent. A deep link, a stale localStorage value or a
   URL parameter cannot smuggle an unentitled account into it.
2. **The switch lives in Settings.** It is a persistent interface preference, so it belongs with the
   account preferences — Settings → Interface — not in the top navigation where a first-time user
   would find it before they found the product.
3. **The default view is not a reduced mode.** It is the product. Advanced adds depth for people who
   want it; it does not unlock capability, and no work is impossible in the default view except the
   inspector-level edits that only matter when you are already deep in a design.

## 7. Naming rule

The default view carries **no mode name in the product**. There is no "Simple mode" label, pill,
badge or menu item anywhere a user can see it. The surface is simply Northstar. Where a control has
to name the distinction, it says **Advanced** for the power-user view and **Standard** for the
default one, and it says so once, in Settings.

`simple` survives only as an internal token — the `ns-shell-mode` storage key, the `shell=simple`
query value, CSS class names, test ids and code comments. Internal names are allowed to be plain
English; product copy is not allowed to be reductive. A user should never be told they are using the
simple version of the thing they paid for.

The per-room inspector depth control in the studio rooms follows the same rule: the default position
is the curated one and is not labelled, and only the deeper position is named Advanced.

## 8. Tier map

| Display name | Plan id | Monthly | `advanced_view` | Notes |
|---|---|---|---|---|
| Whetstone | `foundation` | $39 | — | default view only |
| Mainstay | `scout` | $79 | — | default view only |
| Keystone | `mover` | $129 | **yes (currently)** | see §9 |
| AutothinK | `autothink` | $179 | yes | top tier; also holds `autothink_workspace` |

## 9. Reconciliation — what is on disk today

This document is the target. The running code does not yet match it in four places, and those
differences are listed here rather than smoothed over:

| # | Target | On disk today | Where |
|---|---|---|---|
| 1 | No user-visible "Simple" label | Top nav renders a `Simple \| Advanced` pill | `northstar-os-ui/src/components/ShellModeToggle.jsx` |
| 2 | Studio default depth is unlabelled | Per-room `ModeToggle` renders a "Simple" tab | `northstar-os-ui/src/studio/components/Chrome.jsx` (used by Listing Forge, Product Designer, Social Pulse, Creative Studio, Ad Pilot) |
| 3 | Switch lives in Settings | Switch is in the top nav | `northstar-os-ui/src/components/TopNav.jsx` line 74 |
| 4 | Top tier only | `advanced_view` is granted to `mover` and `autothink` | `shared/subscription-plans.json` |

Items 1–3 are presentation changes with no capability impact. Item 4 changes what a paying tier
receives, so it is a catalogue decision rather than a copy fix, and it is recorded here as open
rather than executed silently.

---

**One line:** Northstar OS is one conversation over a full commerce operator's toolset, wrapped in a
trust layer that never lets a convenience become a permission — and it opens in the view that lets a
new user do real work immediately, with the dense power-user shell reserved for the top tier and
kept in Settings.
