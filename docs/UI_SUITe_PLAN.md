# Northstar OS — UI Suite Overhaul Plan

> Date: 2026-09-15 | Status: Ready for implementation

## Current State Assessment

### What Exists (5 overlapping UIs)
| UI | Path | Lines | Design System |
|----|------|-------|---------------|
| **Analyst's Desk SPA** | `static/northstar-os/` | ~2,800 | Gold/steel/crimson, tokens.css |
| **Research Workbench** | `static/index.html` | ~1,030 | Inline CSS, light/dark toggle |
| **Landing Page** | `static/landing/` | ~244 | Blue/green SaaS (mismatched) |
| **AutothinK Workspace** | `autothink/ui/` | ~851 | Deep space + glass morphism |
| **Legacy Pages** | `root index.html`, `public/` | ~886 | Green accent, different fonts |

### Key Problems
1. **Design inconsistency** — Landing page uses blue/green, SPA uses gold/steel/crimson. Visitors see two different products.
2. **No responsive design** — SPA uses fixed 232px drawer + 268px board + 1080px min table. Broken on tablets/phones.
3. **Massive inline CSS** — Workbench duplicates the design system inline (~1,030 lines).
4. **No login/register page** — Auth exists in API but no UI to use it.
5. **No onboarding flow** — First-time users land on the SPA with no guidance.
6. **Fragmented entry points** — Root `/` serves a legacy marketing page, not the actual product.

---

## Phase A: Unified Design System (tokens + components)

**Goal:** One design language across all pages. Gold/steel/crimson "Analyst's Desk" identity everywhere.

### A1. Extend `tokens.css` with landing page tokens
- Add `--surface`, `--surface-hover`, `--border-subtle` for card-based layouts
- Add `--text-primary`, `--text-secondary`, `--text-muted` semantic aliases
- Add spacing scale: `--sp-1` through `--sp-12` (4px increments)
- Add transition tokens: `--ease-out`, `--duration-fast`, `--duration-normal`

### A2. Create `components.css` — shared UI primitives
Extract and unify these repeated patterns:
- **Buttons** — `.btn`, `.btn-primary`, `.btn-ghost`, `.btn-sm`, `.btn-lg`
- **Cards** — `.card`, `.card-header`, `.card-body`, `.card-footer`
- **Forms** — `.input`, `.select`, `.label`, `.form-group`, `.form-row`
- **Badges** — `.badge`, `.badge-gold`, `.badge-steel`, `.badge-green`, `.badge-red`
- **Tables** — `.data-table`, `.data-table compact` (from services.css, cleaned up)
- **Modals** — `.modal-overlay`, `.modal`, `.modal-header`, `.modal-body`
- **Toasts** — `.toast`, `.toast-success`, `.toast-error`
- **Empty states** — `.empty-state`, `.empty-icon`, `.empty-text`

### A3. Create `layout.css` — responsive shell utilities
- `.page-container` — max-width 1440px, centered, responsive padding
- `.grid-2`, `.grid-3`, `.grid-4` — responsive grid with auto-fit
- `.stack` — vertical spacing utility
- `.sidebar-layout` — drawer + content (responsive: collapses on mobile)
- `.hide-mobile`, `.show-mobile` — responsive visibility

---

## Phase B: Landing Page Rebuild

**Goal:** Professional marketing site that matches the SPA's design language. Converts visitors to signups.

### B1. New landing page (`static/landing/index.html`)
Rebuild from scratch using the Analyst's Desk design system:

```
┌─────────────────────────────────────────────────────────┐
│  NAV: Logo · Features · Pricing · Docs · Login · Sign Up│
├─────────────────────────────────────────────────────────┤
│                                                         │
│  HERO SECTION                                           │
│  "Your AI-Powered Amazon Arbitrage Command Center"      │
│  [Start Free] [Watch Demo]                              │
│  ┌─────────────────────────────────────┐                │
│  │  Live dashboard mockup / screenshot │                │
│  └─────────────────────────────────────┘                │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  TRUST BAR                                              │
│  "Built for sellers who value privacy"                  │
│  Local AI · No cloud · Full audit trail                 │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  5 SERVICE CARDS (gold/steel/crimson accents)           │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐        │
│  │ 🔍   │ │ ✍️   │ │ 📈   │ │ 📱   │ │ 🧠   │        │
│  │Source │ │List  │ │Ad    │ │Social│ │Auto  │        │
│  │Scout  │ │Forge │ │Pilot │ │Pulse │ │thinK │        │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘        │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  HOW IT WORKS (3 steps)                                 │
│  1. Scan Costco → 2. AI Lists → 3. Track & Optimize    │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  COMPARISON TABLE                                       │
│  Northstar vs Helium 10 vs Jungle Scout vs Advigator   │
│  (Privacy, Local AI, Price, Coverage)                   │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  PRICING (4 tiers, gold accent on Scout)               │
│  Foundation $0 · Scout $29 · Mover $79 · AutothinK $149│
│                                                         │
├─────────────────────────────────────────────────────────┤
│  FINAL CTA                                              │
│  "Start finding profitable products today"              │
│  [Get Started Free]                                     │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  FOOTER: Logo · Links · Social · Legal                  │
└─────────────────────────────────────────────────────────┘
```

### B2. Auth pages (`static/auth/login.html`, `static/auth/register.html`)
- Login form: email + password + "Remember me" + "Forgot password?"
- Register form: name + email + password + plan selector
- Both use the Analyst's Desk design system
- Wire to `/api/v1/auth/login` and `/api/v1/auth/register`
- Store JWT in localStorage, redirect to `/northstar-os/`

### B3. Route `/` to landing page
- Change `main.py` root route to serve `static/landing/index.html`
- Move current `static/index.html` (workbench) to `/workbench`
- Keep `/northstar-os/` as the SPA entry

---

## Phase C: SPA Responsiveness

**Goal:** The Analyst's Desk works on tablets (768px+) and degrades gracefully on phones.

### C1. Responsive shell (`shell.css`)
```css
/* Tablet: collapse board, narrower drawer */
@media (max-width: 1200px) {
  #board { display: none; }          /* hide bulletin board */
  #drawer { width: 60px; }          /* icon-only drawer */
  .nav-item span { display: none; } /* hide labels */
}

/* Phone: full-screen views, hamburger nav */
@media (max-width: 768px) {
  #drawer { display: none; }        /* hamburger menu instead */
  #app { flex-direction: column; }
  .ribbon-stats { display: none; }  /* collapse KPI bar */
  #global-search { width: 100%; }  /* full-width search */
}
```

### C2. Responsive tables (`services.css`)
- Horizontal scroll with fade indicators on edges
- Sticky first column (ASIN/product name) on scroll
- Card layout alternative for narrow viewports

### C3. Mobile drawer
- Hamburger button in ribbon (visible < 768px)
- Full-screen overlay drawer on mobile
- Swipe-to-close gesture

---

## Phase D: Dashboard Hub Rebuild

**Goal:** The Hub view becomes a real command center with actionable cards.

### D1. Hub KPI strip redesign
- Larger, more prominent KPI cards
- Sparkline mini-charts in each card
- Color-coded trend arrows (↑ green, ↓ red)
- Time period selector (7d / 30d / 90d)

### D2. Service status cards
- Each service gets a card showing:
  - Status indicator (green dot = healthy)
  - Last run timestamp
  - Quick action button
  - Key metric (e.g., "12 products tracked" for SourceScout)

### D3. Activity feed
- Recent actions list (generated, optimized, published)
- Timestamps and service attribution
- Click to navigate to relevant service

### D4. Quick actions panel
- "Scan new product" → SourceScout
- "Generate listing" → ListingForge
- "Review ad performance" → AdPilot
- "Create social post" → SocialPulse

---

## Phase E: Service View Polish

**Goal:** Each service view feels complete, professional, and aligned.

### E1. SourceScout
- Add loading skeletons for table rows
- Improve filter bar: collapsible advanced filters
- Add column resize handles
- Pinch-to-zoom on mobile for table
- Empty state illustration when no products match filters

### E2. ListingForge
- Side-by-side comparison view (before/after)
- Character count progress bars (green → yellow → red)
- Compliance checklist with checkmarks
- One-click "Apply to Amazon" button (gated)

### E3. AdPilot
- Visual ACoS band chart (not just text)
- Campaign performance trend lines
- Bid change preview before applying
- Negative keyword suggestion cards

### E4. SocialPulse
- Calendar view with drag-and-drop (visual only in demo)
- Image preview thumbnails in content cards
- Platform-specific formatting previews (Instagram square, TikTok vertical)
- Hashtag cloud visualization

### E5. AutothinK
- Inline chat widget (no iframe redirect)
- Command palette (Cmd+K) for quick actions
- AI response streaming visualization
- Service router indicator (which agent is handling)

---

## Phase F: Onboarding & First-Run Experience

**Goal:** New users understand the product in <60 seconds.

### F1. Welcome modal (first visit)
- 3-step tour:
  1. "This is your command center" (Hub)
  2. "Find profitable products here" (SourceScout)
  3. "AI writes your listings" (ListingForge)
- "Skip tour" button
- Stored in localStorage, never shows again

### F2. Empty state illustrations
- Each service gets a custom empty state:
  - SourceScout: "No products tracked yet" + "Scan Costco" CTA
  - ListingForge: "No listings generated" + "Select a product" CTA
  - AdPilot: "No campaigns connected" + "Import campaigns" CTA
  - SocialPulse: "No content scheduled" + "Create first post" CTA

### F3. Progressive disclosure
- Hide advanced features behind "Show advanced" toggle
- Start with simplified views, unlock complexity as users explore
- Tooltips on hover for all technical terms

---

## Implementation Order

| Step | Phase | Files Changed | Effort |
|------|-------|---------------|--------|
| 1 | A1 | `tokens.css` | Small |
| 2 | A2 | New `components.css` | Medium |
| 3 | A3 | New `layout.css` | Medium |
| 4 | B2 | New `auth/login.html`, `auth/register.html` | Medium |
| 5 | B1 | Rebuild `landing/index.html` | Large |
| 6 | B3 | `main.py` route changes | Small |
| 7 | C1-C3 | `shell.css`, new `mobile.css` | Medium |
| 8 | D1-D4 | Rebuild `hub.js`, `index.html` hub section | Medium |
| 9 | E1-E5 | Polish each service view JS | Large |
| 10 | F1-F3 | New `onboarding.js`, empty states | Medium |

---

## Design Principles

1. **One design language** — Gold/steel/crimson everywhere. No blue/green on landing.
2. **Desktop-first, mobile-friendly** — Full experience on desktop, usable on tablet/phone.
3. **Zero network by default** — Demo mode stays completely offline.
4. **Progressive disclosure** — Simple by default, powerful on demand.
5. **Honest states** — Never fabricate data. Show "—" for unknown, "Demo" for fixtures.
6. **Accessibility** — ARIA labels, keyboard navigation, focus management, reduced motion support.
7. **Performance** — No frameworks, no build step, vanilla CSS/JS, <100KB total.

---

## Success Metrics

- [ ] Landing page Lighthouse score >90 (Performance, Accessibility, Best Practices)
- [ ] SPA renders correctly at 768px, 1024px, 1440px, 1920px widths
- [ ] All pages share the same `tokens.css` design tokens
- [ ] Login/register flow works end-to-end (API → JWT → redirect)
- [ ] No inline CSS >50 lines in any HTML file
- [ ] All interactive elements have ARIA labels
- [ ] Total CSS+JS <150KB uncompressed
