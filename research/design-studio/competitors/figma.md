# Figma ? Competitor Deep Dive

> Track A of the Northstar Design Studio research corpus. Every claim carries a
> source URL and a tag: [documented] (vendor's own docs/pricing), [observed]
> (seen in product, demo, or video), [inferred] (derived reasoning or
> third-party claim, not confirmed by the vendor).
> Pulled at: 2026-10-10.

## 1. What it is, who it's for, pricing tiers and generation limits

Figma is a browser-based collaborative design tool spanning UI design
(Figma Design), whiteboarding (FigJam), presentations (Slides), animation
(Motion), site building (Sites), vector drawing (Draw), buzz/marketing assets
(Buzz), AI generation (Make) and developer handoff (Dev Mode). Audience is
product/UX teams, not Amazon sellers.

PRICING (USD, documented on figma.com/pricing) [documented]:
- **Starter** free: unlimited drafts, UI kits and templates, basic design file
  inspection, **150 AI credits/day up to 500 AI credits/month**, Starter 3-file
  limit for Figma Design and Figma Sites.
- **Professional** billed annually: Full seat $16/mo (+3,000 AI credits/mo),
  Dev seat $12/mo (+500), Collab seat $3/mo (+500). Adds unlimited files and
  projects for one team, team-wide design libraries, advanced Dev Mode
  inspection and MCP Server, advanced prototyping, prototype sharing
  permissions, private folders, 20 variable modes.
- **Organization**: Full $55/mo (+3,500 AI credits), Dev $25 (+500), Collab $5
  (+500). Unlimited variable modes via extended collections.
- **Enterprise**: Full $90/mo (+4,250 AI credits), Dev $35 (+500), Collab $5
  (+500).

GENERATION LIMITS [documented]: credits are monthly and do not roll over
between tiers. Seat type determines product access: **Full** = Design, Dev Mode,
FigJam, Slides, Make, Draw; **Dev** = Dev Mode, FigJam, Slides; **Collab** =
FigJam, Slides; **View** (free) = view and comment. Full is the only seat that
can edit design files or use Make outside drafts.

## 2. Feature inventory

| Feature | How it works | Source | Tier |
|---|---|---|---|
| Auto layout | Frames that reflow responsively when content or size changes | figma.com/pricing | all plans |
| Components + variants | One master component with named property variants (state, size, colour) | figma.com/pricing | all plans |
| Team-wide design libraries | Shared components, styles and variables across a team | figma.com/pricing | Professional+ |
| Variables + variable modes | Design tokens with mode switching; 10 modes Starter, 20 Pro, unlimited via extended collections | figma.com/pricing | varies |
| Dev Mode + MCP handoff | Specs, measurements, annotations and asset export for developers; MCP server | figma.com/pricing | Dev or Full seat on paid |
| FigJam | Whiteboard with tables, code blocks, diagramming, voting, AI Summarize/Generate/Sort | figma.com/pricing | every seat |
| Figma Make | AI generation of UI from prompt/URL/screenshot | figma.com/pricing | Full seat |
| Figma Motion (beta) | Animation timeline, motion systems authoring, animation export, high-res video export | figma.com/pricing | listed |
| Figma Draw | Enhanced vector editing, custom brushes, text on a path | figma.com/pricing | all plans |
| Figma Sites (beta) | Blocks/embeds, breakpoints, interactions, CMS, publishing | figma.com/pricing | paid to publish |
| Interactive prototypes | Advanced animations, transitions, overlays, conditional logic, expressions, variables | figma.com/pricing | tier varies |
| Code Connect | Map design components to production code components | figma.com/pricing | UI kits on Professional |
| Compare changes | Diff design revisions | figma.com/pricing | Dev Mode |
| VS Code extension | Move specs into the editor | figma.com/pricing | paid |
| Community plugins | Third-party plugins (community-only on lower plans) | figma.com/pricing | varies |

## 3. User workflow, step by step (clicks to first output)

Figma's first output is fast for a designer (place a frame, draw, done) but
slow for a non-designer. The Make path (prompt ? UI) and the plugin path
(generate UI from a prompt, turn a URL into editable layers, convert a
screenshot into frames without leaving Figma) are the two shortcuts. Notably,
Figma can ROUND-TRIP: screens exported from a third-party generator come back
as auto-layout frames with editable text, real fills and named layers, and
import from Figma brings an existing frame back with its auto-layout, text
styles and colours. That import/export fidelity is the standard the Design
Studio's asset library must meet.

## 4. UI / layout patterns

Canvas-centric editor with a left Layers panel, a right Design/Prototype/
Inspect tab panel, a top toolbar, a bottom-page strip, and inline comment
threads pinned to canvas objects. Multiplayer cursors are the signature
interaction. FigJam is a separate infinite-canvas whiteboard surface with
stickers and voting. Dev Mode is a distinct read-only surface for developers
with a compare-changes diff. The pattern worth copying: the SAME file has
multiple purpose-built surfaces for different roles, and the role determines
which surface you land in.

## 5. What users love / hate

No aggregated G2 complaint theme list was retrieved in this pass (the
comparable quantified source available was Canva's). Documented seller-voice
signals found: Figma's iOS UX complaint rate is 5.6%, roughly half of Canva's
10.4% [documented, App Imp peer comparison]. Real community complaint on seat
pricing: "Dev mode pricing is 35$ in an enterprise plan where you can have more
than 75% of the available features useless" (Figma forum) ? i.e. seat granularity
is too coarse for a role that only inspects. Third-party analysis notes Dev Mode
is unavailable on Starter and requires a Dev or Full seat on paid, and that a
$3 Collab seat is the cheapest way to give someone full FigJam.

## 6. Gaps for Amazon sellers specifically

Amazon-relevant gaps:
1. **No Amazon anything.** No image spec validation, no A+ module system, no
   Store tile sizes, no compliance concept.
2. **Priced and scoped for software teams.** A retail-arbitrage seller does not
   have a "Full seat" role or a design system.
3. **Not a raster production tool.** Figma is vector/UI oriented; it is the wrong
   tool for photorealistic product scenes and 2000x2000 marketplace images.
4. **AI credits are small and generic** (500-4,250/mo) with no product-image
   specialisation.
5. **No product-record linkage.** Nothing connects a canvas to an ASIN, a
   listing, or a buy-box product.

## 7. Output quality notes and known failure modes

Figma's relevant strength is not generation quality but STRUCTURAL quality:
auto-layout, components/variants and variables are exactly the primitives a
Design Studio needs to express "one master that renders at every Amazon
placement size" and "one component with 6 child-ASIN variants". Its known
failure modes for our purposes: heavy files get slow; a non-designer cannot
find the first click; and there is no notion of a raster output spec.
