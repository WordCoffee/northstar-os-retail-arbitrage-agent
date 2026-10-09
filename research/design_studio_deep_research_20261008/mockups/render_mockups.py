"""NorthstarOS Design Studio — concept renders.

Run:  python research/design_studio_deep_research_20261008/mockups/render_mockups.py

Emits standalone .svg files into ./out/. Every screen is drawn with the real
tokens in svgkit.py, and every "generated asset" surface is drawn as the SAME
honest placeholder the shipped room uses — these renders show layout and
information architecture, not fabricated imagery.
"""
from __future__ import annotations

import os

from svgkit import (
    CLAY, DIVIDER, DIVIDER_MID, FOREST, FOREST_GLOW, INK, INK_FAINT, INK_MID, INK_SOFT,
    MONO, OCHRE, PAPER, PINE, PINE_DEEP, PINE_LIGHT, SAGE, SAGE_SOFT, SERIF, STATUS_ERROR,
    STATUS_OK, STATUS_OK_SOFT, STATUS_UNKNOWN, STATUS_UNKNOWN_SOFT, STATUS_WARN,
    STATUS_WARN_SOFT, SURFACE, SURFACE_ACTIVE, SURFACE_RAISED, UI, Canvas, arrow, btn, card,
    checkered, field, footer, format_grid, hatched_dims, inspector, meter, page_header, pill,
    rail_button, section, spec_table, stage, stat, swatch, tabs, thumb, topnav,
)

# svgkit exposes text/line/rect/path/circle as Canvas methods; the renders below
# read better with the same module-level call shape as every other primitive.
def text(c, x, y, s, **kw):
    c.text(x, y, s, **kw)


def line(c, x1, y1, x2, y2, **kw):
    c.line(x1, y1, x2, y2, **kw)


def rect(c, x, y, w, h, **kw):
    c.rect(x, y, w, h, **kw)


def circle(c, cx, cy, r, **kw):
    c.circle(cx, cy, r, **kw)


def path(c, d, **kw):
    c.path(d, **kw)


HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

DEFS = """<defs>
<pattern id="hatch" width="12" height="12" patternUnits="userSpaceOnUse"
  patternTransform="rotate(45)"><rect width="6" height="12"
  fill="rgba(138,138,122,0.05)"/></pattern>
</defs>"""

STATIONS = [
    ("layers", "Listing", "main · A+ · brand story"),
    ("bolt", "Ads", "SB · SD · SP"),
    ("video", "Video", "url-to-video · UGC"),
    ("calendar", "Social", "posts · carousel"),
    ("cube", "Product", "concepts · dieline"),
    ("palette", "Brand", "kit · voice · claims"),
]

ICONS = {
    "layers": "M8 1l6 3-6 3-6-3z M2 8l6 3 6-3 M2 11.5l6 3 6-3",
    "bolt": "M9 1L3 9h4l-1 6 6-8H8z",
    "video": "M2 4h8v8H2z M10 7l4-2.5v7L10 9z",
    "calendar": "M2 5h12v9H2z M2 8h12 M5 3v3 M11 3v3",
    "cube": "M2 5l6-3 6 3v6l-6 3-6-3z M8 2v12 M2 5l6 3 6-3",
    "palette": "M8 2a6 6 0 000 12c1.2 0 1.8-.8 1.8-1.8 0-1.4 1-2 2.2-2H14a3 3 0 003-3A6 6 0 008 2z",
    "shield": "M8 1l5 2v5c0 3.5-3 6-5 7-2-1-5-3.5-5-7V3z",
    "search": "M7 1a6 6 0 100 12A6 6 0 007 1z M11 11l4 4",
    "check": "M2 8.5l4 4 8-9",
    "wand": "M3 13L11 5 M12 2l.7 1.8L14.5 4.5l-1.8.7L12 7l-.7-1.8L9.5 4.5l1.8-.7z",
    "type": "M3 4h10M8 4v9M6 13h4",
    "box": "M3 5l5-2 5 2v7l-5 2-5-2z",
    "tag": "M2 2h6l6 6-6 6-6-6z M5 5h.01",
    "chart": "M2 12V8M6 12V4M10 12V6M14 12V2",
    "eye": "M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z M8 6a2 2 0 100 4 2 2 0 000-4",
    "clock": "M8 1a7 7 0 100 14A7 7 0 008 1z M8 4v4l3 2",
    "globe": "M8 1a7 7 0 100 14A7 7 0 008 1z M1 8h14 M8 1c-3 2-3 11 0 14 M8 1c3 2 3 11 0 14",
    "list": "M3 4h10M3 8h10M3 12h7",
    "sparkle": "M8 1l1.6 4.4L14 7l-4.4 1.6L8 13l-1.6-4.4L2 7l4.4-1.6z",
    "key": "M4 8a4 4 0 118 0 4 4 0 01-8 0z M10 10l4 4",
}


def ic(c, cx, cy, name, color=INK_SOFT, size=16):
    d = ICONS.get(name, ICONS["layers"])
    c.add(f'<g transform="translate({cx - size/2:.2f},{cy - size/2:.2f}) scale({size/16:.3f})">'
          f'<path d="M {d}" fill="none" stroke="{color}" stroke-width="1.5" '
          f'stroke-linecap="round" stroke-linejoin="round"/></g>')


def tw(s, size):
    narrow = set("iljItf.,:;'\"|!()[]{}-")
    wide = set("MWmw@%")
    u = 0.0
    for ch in str(s):
        if ch in narrow:
            u += 0.30
        elif ch in wide:
            u += 0.90
        elif ch.isupper():
            u += 0.68
        elif ch == " ":
            u += 0.29
        else:
            u += 0.53
    return u * size


def write(c, name, title, subtitle=""):
    os.makedirs(OUT, exist_ok=True)
    body = "".join(c.parts)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{c.w}" height="{c.h}" '
           f'viewBox="0 0 {c.w} {c.h}" font-family="{UI}">'
           f"<title>{title}</title><desc>{subtitle}</desc>"
           f'{DEFS}<rect width="{c.w}" height="{c.h}" fill="{PAPER}"/>{body}</svg>\n')
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
        fh.write(svg)
    print("wrote", name)


# ── shared inspector helpers ────────────────────────────────────────────────

def krow(c, x, y, w, k, v, mono=False, tone=None):
    text(c, x, y, k, size=10.5, color=INK_SOFT)
    col = {"ok": STATUS_OK, "warn": STATUS_WARN, "error": CLAY, "forest": FOREST}.get(tone, INK)
    text(c, x + w, y, v, size=10.5, color=col, font=MONO if mono else UI, anchor="end")
    line(c, x, y + 6, x + w, y + 6, stroke=DIVIDER)
    return y + 18


def check(c, x, y, w, ok, label, note=""):
    ic(c, x + 6, y + 4, "check" if ok else "shield", STATUS_OK if ok else CLAY, 12)
    text(c, x + 20, y + 8, label, size=10.5, color=INK, weight=500)
    text(c, x + w, y + 8, "PASS" if ok else "BLOCK", size=9,
         color=STATUS_OK if ok else CLAY, font=MONO, anchor="end")
    if note:
        text(c, x + 20, y + 22, note, size=9, color=INK_FAINT)
        return y + 32
    return y + 20


def term_chip(c, x, y, term, tier, orders, active=False):
    w = max(tw(term, 10.5) + 24, 96)
    c.rect(x, y, w, 26, fill=FOREST_GLOW if active else SURFACE_RAISED,
           stroke=FOREST if active else DIVIDER, rx=13)
    text(c, x + 10, y + 17, term, size=10.5, color=PINE_DEEP if active else INK, weight=500)
    text(c, x + w - 9, y + 17, f"{orders} ord", size=8.5, color=INK_FAINT, font=MONO,
         anchor="end")
    return x + w + 6


# ═══════════════════════════════════════════════════════════════════════════
# 00 — CURRENT STATE
# ═══════════════════════════════════════════════════════════════════════════

def r00_current():
    c = Canvas(1440, 900)
    topnav(c, active="Creative Studio")
    y = 56
    y = page_header(c, 28, y + 16, "Creative Studio",
                    "Creative operations — work briefs, image and short-clip requests, "
                    "reference assets, variants, and export bundles.",
                    actions=[("New Brief", "secondary"), ("Compose Image", "ghost"),
                             ("Export Bundle", "ghost")])
    ny = 118
    c.rect(28, ny, 1384, 54, fill=SURFACE_RAISED, stroke=DIVIDER_MID, rx=8)
    pill(c, 42, ny + 9, "sample", "unknown", size=8.5, h=16, pad=7)
    text(c, 102, ny + 21, "This room is a local workflow workspace", size=11.5, color=PINE_DEEP,
         weight=600)
    text(c, 42, ny + 40, "Briefs, requests, assets, variants, and bundles are real records you "
                         "create here and are stored in this browser. No image or video is "
                         "generated or depicted — there is no wired creative provider in this "
                         "build.", size=10.5, color=INK_MID)
    y = ny + 70

    by = y
    c.rect(28, by, 1384, 44, fill=SURFACE, stroke=DIVIDER, rx=12)
    text(c, 42, by + 27, "Active brief", size=11, color=INK_SOFT)
    bx = 118
    for name in ["Set A Launch — Ad Creatives", "Q4 Seasonal Bundle",
                 "Installation Guide Refresh"]:
        on = name.startswith("Set A")
        w = 200 if on else tw(name, 11) + 24
        c.rect(bx, by + 8, w, 28, fill=FOREST_GLOW if on else "none",
               stroke=FOREST if on else DIVIDER_MID, rx=999)
        text(c, bx + 12, by + 27, name, size=11, color=FOREST if on else INK_MID,
             weight=600 if on else 400)
        bx += w + 8
    pill(c, 1332, by + 13, "Active", "warn")

    ty = by + 60
    tabs(c, 28, ty, ["Briefs", "Image Composer", "Video / Shorts", "Production Queue",
                     "Variants & History", "Assets", "Exports", "Library"], "Briefs")

    cy = ty + 46
    briefs = [
        ("Set A Launch — Ad Creatives", "Drive awareness", "Homeowners 30–55", "Word Coffee",
         ["Ad creative", "Social variant", "Listing imagery"], 6, "Active", "warn"),
        ("Q4 Seasonal Bundle", "Seasonal promo", "Existing customers", "Word Coffee",
         ["Social variant", "Email hero"], 4, "Draft", "muted"),
        ("Installation Guide Refresh", "Support conversion", "New buyers", "Mogra Organics",
         ["Listing imagery", "A+ content"], 3, "In Review", "ochre"),
    ]
    cw = (1384 - 2 * 20) / 3
    for i, (name, obj, aud, brand, fmts, deliv, st, stk) in enumerate(briefs):
        x = 28 + i * (cw + 20)
        px, py = card(c, x, cy, cw, 178, pad=14)
        pill(c, px, py, st, stk)
        text(c, px, py + 36, name, size=13, color=PINE_DEEP, weight=600)
        text(c, px, py + 56, f"{obj} · {aud}", size=11.5, color=INK_MID)
        text(c, px, py + 74, brand, size=10.5, color=INK_FAINT)
        fx = px
        for f in fmts:
            fx = pill(c, fx, py + 86, f, "muted", size=9, h=17, pad=7) + 5
        line(c, px, py + 118, px + cw - 28, py + 118, stroke=DIVIDER)
        text(c, px, py + 138, f"{deliv} deliverables", size=10.5, color=INK_SOFT)
        btn(c, px + cw - 28 - 58, py + 124, "Open", "ghost", size=10, h=26, pad=10)

    dy = cy + 194
    px, py = card(c, 28, dy, 900, 150, pad=18)
    text(c, px, py, "Active Brief — Set A Launch — Ad Creatives", size=15, color=PINE_DEEP,
         font=SERIF, weight=600)
    pill(c, px + 812, py - 12, "Active", "warn")
    for i, (k, v) in enumerate([("Objective", "Drive awareness"),
                                ("Audience", "Homeowners 30–55"),
                                ("Brand", "Word Coffee"),
                                ("Formats", "Ad creative, Social variant")]):
        text(c, px + i * 218, py + 32, k.upper(), size=8.5, color=INK_SOFT, spacing=0.05)
        text(c, px + i * 218, py + 52, v, size=12, color=INK, weight=500)
    text(c, px, py + 90, "Hero + feature set, matched brand kit.", size=10.5, color=INK_FAINT)

    px2, py2 = card(c, 948, dy, 464, 150, pad=18)
    text(c, px2, py2, "Preview", size=15, color=PINE_DEEP, font=SERIF, weight=600)
    pill(c, px2 + 348, py2 - 12, "provider required", "unknown")
    thumb(c, px2, py2 + 16, 428, 64, "1:1 · AD CREATIVE", "No generated asset — provider required")

    footer(c, 856,
           "Render 00 — CURRENT STATE. Reconstructed faithfully from "
           "northstar-os-ui/src/pages/internal/CreativeStudio.jsx (route /creative-studio, nav "
           "status 'Concept'). Eight tabs of real local records; every preview is the room's own "
           "honest placeholder. No canvas, no layers, no format presets, no Amazon rules, no "
           "keyword binding.")
    write(c, "00-current-creative-studio.svg", "Current state — Creative Studio room",
          "The shipped /creative-studio Briefs tab: a local workflow-records workspace with a "
          "hollow middle. No design engine is mounted.")


# ═══════════════════════════════════════════════════════════════════════════
# SHARED SHELL
# ═══════════════════════════════════════════════════════════════════════════

def shell(c, station, stage_label, stage_dims, stage_badge, draw_stage, inspector_title,
          draw_inspector, subtitle, actions=(("Export", "ghost"), ("Run pre-flight", "primary")),
          rail_counts=None, mode="Advanced", preflight="", badge_kind="error"):
    topnav(c, active="Design Studio")
    y = 56
    y = page_header(c, 28, y + 14, "Design Studio", subtitle, actions=list(actions))

    sy = y + 6
    c.rect(28, sy, 1384, 62, fill=SURFACE, stroke=DIVIDER, rx=12)
    text(c, 44, sy + 22, "CONTENT TYPE", size=9, color=INK_SOFT, weight=700, spacing=0.09)
    text(c, 44, sy + 42, "Formats, templates, compliance rules and brief fields are all derived "
                         "from this one choice.", size=10, color=INK_FAINT)
    sx = 470
    for icn, label, note in STATIONS:
        on = label == station
        w = 142
        c.rect(sx, sy + 10, w, 42, fill=FOREST_GLOW if on else SURFACE_RAISED,
               stroke=FOREST if on else DIVIDER, rx=8)
        ic(c, sx + 22, sy + 31, icn, FOREST if on else INK_SOFT, 15)
        text(c, sx + 40, sy + 27, label, size=11.5, color=PINE_DEEP if on else INK_MID,
             weight=600 if on else 500)
        text(c, sx + 40, sy + 41, note, size=8.5, color=INK_FAINT)
        sx += w + 8

    c.rect(sx + 8, sy + 16, 122, 30, fill=SURFACE_ACTIVE, stroke=DIVIDER, rx=999)
    for i, m in enumerate(["Simple", "Advanced"]):
        on = m == mode
        if on:
            c.rect(sx + 12 + i * 58, sy + 19, 54, 24, fill=SURFACE, stroke=DIVIDER, rx=999)
        text(c, sx + 39 + i * 58, sy + 35, m, size=11, color=PINE_DEEP if on else INK_MID,
             weight=600 if on else 400, anchor="middle")

    y = sy + 62 + 12
    SH = 566

    c.rect(28, y, 62, SH, fill=SURFACE, stroke=DIVIDER, rx=12)
    for i, (icn, label, _n) in enumerate(STATIONS):
        rail_button(c, 34, y + 8 + i * 60, 50, icn, label, label == station,
                    (rail_counts or {}).get(label))
    ry = y + 8 + 6 * 60
    line(c, 34, ry - 8, 84, ry - 8, stroke=DIVIDER)
    rail_button(c, 34, ry, 50, "shield", "Pre-flight")
    rail_button(c, 34, ry + 58, 50, "key", "Keywords")
    rail_button(c, 34, ry + 116, 50, "box", "Assets", 18)

    stage(c, 104, y, 820, SH, label=stage_label, dims=stage_dims, badge=stage_badge,
          children=draw_stage)

    ix, iy, iw = inspector(c, 936, y, 476, SH, inspector_title)
    draw_inspector(ix, iy + 8, iw)

    fy = y + SH - 32
    text(c, 118, fy + 21, "PRE-FLIGHT", size=8.5, color="#a8b3a4", font=MONO, spacing=0.06)
    text(c, 196, fy + 21, preflight, size=10.5, color="#a8b3a4")
    if badge_kind:
        pill(c, 806, fy + 8, badge_kind, "error" if badge_kind.startswith("1") else "ok",
             size=8.5, h=16, pad=7)
    return y + SH
# ═══════════════════════════════════════════════════════════════════════════
# 02 — LISTING STATION
# ═══════════════════════════════════════════════════════════════════════════

def r02_listing():
    c = Canvas(1440, 900)

    def draw_stage():
        checkered(c, 292, 206, 424, 424)
        c.rect(292, 206, 424, 424, fill=SURFACE, stroke=DIVIDER_MID)
        c.rect(310, 224, 388, 388, fill="rgba(138,138,122,0.10)", stroke=DIVIDER_MID, dash="6 4")
        text(c, 504, 406, "PRODUCT COMPOSITE", size=11, color=INK_SOFT, font=MONO,
             anchor="middle", spacing=0.06)
        text(c, 504, 424, "operator packshot · reference-locked", size=9, color=INK_FAINT,
             anchor="middle")
        c.rect(292, 206, 424, 424, fill="none", stroke=OCHRE, sw=1, opacity=0.5)
        for i in (1, 2):
            line(c, 292 + 141 * i, 206, 292 + 141 * i, 630, stroke=OCHRE, sw=0.7, dash="4 4")
        text(c, 300, 228, "85% FILL GUIDE", size=8, color=OCHRE, font=MONO, spacing=0.06)

        text(c, 104, 664, "SECONDARY IMAGES", size=8.5, color="#a8b3a4", font=MONO, spacing=0.06)
        for i, lbl in enumerate(["1 · SIZE / SCALE", "2 · IN USE", "3 · INGREDIENTS",
                                 "4 · WHAT'S INCLUDED", "5 · COMPARISON", "6 · HOW TO USE"]):
            thumb(c, 104 + i * 130, 676, 120, 74, lbl)
        text(c, 104, 774, "500–10,000 px on the longest side, >1,000 px preferred for zoom · "
                          "PNG / JPG / TIFF / non-animated GIF", size=9.5, color="#8a8a7a")

        text(c, 104, 806, "A+ CONTENT", size=8.5, color="#a8b3a4", font=MONO, spacing=0.06)
        # Specs below are the VERIFIED Amazon figures from AMAZON_REQUIREMENTS.md §4-§5
        # (Amazon's own module-guide PDFs, S410/S413), not the repo's presets.js values.
        for i, (lbl, note) in enumerate([("PREMIUM FULL IMAGE 1464×600", "brand story"),
                                         ("BASIC · 4 IMAGES & TEXT 200×200", "feature tiles"),
                                         ("COMPARISON CHART 150×300", "vs. baseline"),
                                         ("HOTSPOTS 1464×600", "interactive points")]):
            thumb(c, 104 + i * 205, 818, 190, 62, lbl, note)

    def insp(ix, iy, iw):
        y = iy
        y = section(c, ix, y, iw, "Image set", "6 of 9",
                    body=lambda yy: _listing_set(c, ix, yy, iw))
        y = section(c, ix, y, iw, "Amazon pre-flight", "1 BLOCKER",
                    body=lambda yy: _listing_preflight(c, ix, yy, iw))
        y = section(c, ix, y, iw, "Bound search terms", "3",
                    body=lambda yy: _listing_terms(c, ix, yy, iw))
        y = section(c, ix, y, iw, "Claims guardrail", "1 flagged",
                    body=lambda yy: _listing_claims(c, ix, yy, iw))

    shell(c, "Listing", "Main image · ASIN B0C7QX4M2P", "1600×1600", ("compliant", "ok"),
          draw_stage, "Listing inspector", insp,
          "Listing station — main image, secondary set, A+ content, Brand Story and Storefront, "
          "each rendered against the live Amazon requirement set.",
          rail_counts={"Listing": 6, "Ads": 12, "Video": 4, "Social": 9, "Product": 3, "Brand": 1},
          preflight="Main image 1600×1600 PNG · product fills ≥85% of frame · no text, no badge, "
                    "no inset · claims: 1 unsupported",
          badge_kind="1 blocker")

    footer(c, 852,
           "Render 02 — PROPOSED: Listing station. The engine that draws this already exists "
           "(northstar-os-ui/src/studio/**, currently orphaned and uncommitted). What is NEW: the "
           "Amazon pre-flight section, the bound search terms, and the claims guardrail. Product "
           "composites stay the operator's own photography — no fabricated product imagery.")
    write(c, "02-listing-station.svg", "Proposed — Design Studio listing station",
          "Listing content-type: main image with Amazon fill guide, secondary image set, A+ module "
          "band, and an inspector carrying the compliance pre-flight, bound search terms and claims "
          "guardrail.")


def _listing_set(c, x, y, w):
    for k, v in [("Master doc", "DOC-MAIN-B0C7QX"),
                 ("Format", "1600×1600 PNG · sRGB"),
                 ("Longest side", "1600 px — inside 500–10,000, above 1,000 zoom floor"),
                 ("Background", "pure white — required on MAIN"),
                 ("Product fill", "87% of frame — Amazon floor is 85%"),
                 ("Text on image", "none — MAIN forbids text, logos, borders, badges")]:
        y = krow(c, x, y, w, k, v, tone="ok" if "floor" in v or "forbids" in v else None)
    text(c, x, y + 8, "Reference-locked: every secondary and A+ asset is composited from the same "
                      "packshot so the product never drifts between panels.", size=9,
         color=INK_FAINT)
    return y + 22


def _listing_preflight(c, x, y, w):
    y = check(c, x, y, w, True, "Raster size", "1600 px longest side; Amazon range 500–10,000")
    y = check(c, x, y, w, True, "File type", "PNG accepted; animated GIF is not")
    y = check(c, x, y, w, True, "Product fill ≥85%", "measured 87% — above the floor")
    y = check(c, x, y, w, True, "White background", "pure white, no colour block")
    y = check(c, x, y, w, True, "No text / logo / border / badge", "prohibited on the MAIN image")
    y = check(c, x, y, w, True, "Product out of packaging", "no box or bag in frame")
    y = check(c, x, y, w, False, "Claim: 'clinically proven'",
              "no evidence attached — add a source or remove")
    y = check(c, x, y, w, True, "Brand kit", "Pine & Bone · ink and accent applied")
    text(c, x, y + 6, "Amazon's own warning: non-compliant images can lead to listing suppression "
                      "from search results, and content failing validation will not start a "
                      "Manage Your Experiments test as scheduled.", size=9, color=INK_FAINT)
    return y + 26


def _listing_terms(c, x, y, w):
    text(c, x, y + 2, "Each asset is bound to the search terms it is meant to win.", size=9,
         color=INK_FAINT)
    y += 16
    tx = x
    for t, orders in [("organic cacao powder", 41), ("non-alkalized cocoa", 18)]:
        tx = term_chip(c, tx, y, t, "", orders, active=True)
    y += 32
    tx = x
    for t, orders in [("cacao powder bulk", 6), ("raw cocoa powder", 4)]:
        tx = term_chip(c, tx, y, t, "", orders)
    y += 34
    y = krow(c, x, y, w, "On-image copy", "indexed term match", tone="ok")
    return y + 4


def _listing_claims(c, x, y, w):
    y = krow(c, x, y, w, "Approved", "12 phrases in library")
    y = krow(c, x, y, w, "Prohibited", "31 phrases blocked", tone="error")
    y = krow(c, x, y, w, "Needs evidence", "1 claim flagged", tone="warn")
    text(c, x, y + 8, "A claim with no attached evidence cannot pass pre-flight. That is the "
                      "account-safety trade: fewer claims, safer listing.", size=9, color=INK_FAINT)
    return y + 24
# ═══════════════════════════════════════════════════════════════════════════
# 03 — ADS STATION
# ═══════════════════════════════════════════════════════════════════════════

def r03_ads():
    c = Canvas(1440, 900)

    def draw_stage():
        text(c, 104, 224, "AD FORMATS", size=8.5, color="#a8b3a4", font=MONO, spacing=0.06)
        fmts = [("Sponsored Brands", "1200×628", "headline + logo"),
                ("Sponsored Display", "1200×628", "custom image"),
                ("Sponsored Products", "square crop", "from listing"),
                ("Store spotlight", "1920×640", "hero band")]
        for i, (n, d, note) in enumerate(fmts):
            x = 104 + i * 205
            on = i == 0
            c.rect(x, 234, 190, 96, fill=FOREST_GLOW if on else "rgba(255,255,255,0.05)",
                   stroke=FOREST if on else "rgba(255,255,255,0.12)", rx=8)
            text(c, x + 12, 256, n, size=10.5, color="#f5f0e8" if on else "#cfd6ca", weight=600)
            text(c, x + 12, 272, d, size=9, color="#a8b3a4", font=MONO)
            text(c, x + 12, 288, note, size=9, color="#8a9a86")
            thumb(c, x + 12, 298, 166, 22, "")
        # hero canvas
        checkered(c, 104, 350, 490, 330)
        c.rect(104, 350, 490, 330, fill=SURFACE, stroke=DIVIDER_MID)
        c.rect(104, 350, 245, 330, fill="#e8e2d8")
        c.rect(126, 392, 200, 246, fill="rgba(138,138,122,0.12)", stroke=DIVIDER_MID, dash="6 4")
        text(c, 226, 508, "PRODUCT", size=10, color=INK_SOFT, font=MONO, anchor="middle",
             spacing=0.06)
        text(c, 226, 524, "reference-locked", size=8.5, color=INK_FAINT, anchor="middle")
        text(c, 372, 392, "Cold-brew ready in", size=9, color=INK_SOFT)
        text(c, 372, 414, "30 SECONDS", size=20, color=PINE_DEEP, font=SERIF, weight=700)
        text(c, 372, 440, "No grit. No clumps. Just cacao.", size=10, color=INK_MID)
        c.rect(372, 456, 116, 26, fill=FOREST, rx=13)
        text(c, 430, 473, "SHOP NOW", size=9.5, color="#ffffff", weight=600, anchor="middle")
        text(c, 372, 500, "Headline bound to: cold brew cacao", size=8.5, color=INK_FAINT,
             font=MONO)
        text(c, 372, 514, "Body bound to: instant cacao powder", size=8.5, color=INK_FAINT,
             font=MONO)

        # variant row
        text(c, 104, 708, "VARIANTS", size=8.5, color="#a8b3a4", font=MONO, spacing=0.06)
        for i, (lbl, note) in enumerate([("A · CONTROL", "current live"),
                                         ("B · 30 SECONDS HOOK", "word-level variant"),
                                         ("C · INGREDIENT LED", "benefit variant"),
                                         ("D · SOCIAL PROOF", "review-count variant")]):
            thumb(c, 104 + i * 205, 720, 190, 74, lbl, note)

    def insp(ix, iy, iw):
        y = iy
        y = section(c, ix, y, iw, "Campaign binding", "SB · auto",
                    body=lambda yy: _ads_campaign(c, ix, yy, iw))
        y = section(c, ix, y, iw, "Search-term hook", "3 terms",
                    body=lambda yy: _ads_terms(c, ix, yy, iw))
        y = section(c, ix, y, iw, "Listing consistency", "1 mismatch",
                    body=lambda yy: _ads_consistency(c, ix, yy, iw))
        y = section(c, ix, y, iw, "Experiment slot", "A / B",
                    body=lambda yy: _ads_experiment(c, ix, yy, iw))

    shell(c, "Ads", "Sponsored Brands · campaign Set A", "1200×628", ("in policy", "ok"),
          draw_stage, "Ads inspector", insp,
          "Ads station — Sponsored Brands, Sponsored Display and Sponsored Products creative, plus "
          "off-Amazon static and video, each variant tied to the ad data it came from.",
          rail_counts={"Listing": 6, "Ads": 12, "Video": 4, "Social": 9, "Product": 3, "Brand": 1},
          preflight="SB 1200×628 · headline ≤50 chars · no price or claim · destination URL "
                    "verified · listing consistency: 1 mismatch",
          badge_kind="1 warning")

    footer(c, 852,
           "Render 03 — PROPOSED: Ads station. The ad copy and campaign data already exist in the "
           "repo (Northstar_backend/ad_pilot.py, importers/ads_api_importer.py → keyword_performance "
           "with searchTerm / impressions / clicks / spend / orders / sales). What is NEW: binding "
           "each creative variant to the search term it targets, the listing-to-ad consistency "
           "check, and the experiment slot.")
    write(c, "03-ads-station.svg", "Proposed — Design Studio ads station",
          "Ads content-type: Amazon ad format picker, hero canvas with search-term-bound copy, "
          "variant row for A/B testing, and an inspector carrying campaign binding, search-term "
          "hooks, listing consistency and experiment slot.")


def _ads_campaign(c, x, y, w):
    for k, v in [("Campaign", "Set A — awareness"), ("Ad group", "auto-targeted"),
                 ("Placement", "top of search"), ("Bid", "$0.84"),
                 ("Budget remaining", "$41.20")]:
        y = krow(c, x, y, w, k, v, mono=True)
    return y + 2


def _ads_terms(c, x, y, w):
    tx = x
    for t, o in [("cold brew cacao", 22), ("instant cacao powder", 15)]:
        tx = term_chip(c, tx, y, t, "", o, active=True)
    y += 32
    tx = x
    for t, o in [("cacao protein shake", 9), ("sugar free cocoa", 3)]:
        tx = term_chip(c, tx, y, t, "", o)
    y += 34
    y = krow(c, x, y, w, "Image-text SEO", "on-image copy matches term", tone="ok")
    return y + 4


def _ads_consistency(c, x, y, w):
    y = check(c, x, y, w, True, "Price shown matches listing")
    y = check(c, x, y, w, True, "Pack count matches listing", "12 ct on both")
    y = check(c, x, y, w, True, "Claim set is a subset of approved")
    y = check(c, x, y, w, False, "Listing says 'unsweetened', ad says 'no sugar'",
              "different claims — ad suppression risk")
    return y + 4


def _ads_experiment(c, x, y, w):
    y = krow(c, x, y, w, "Slot", "A / B — headline variant")
    y = krow(c, x, y, w, "Tests the", "primary image + headline pair")
    y = krow(c, x, y, w, "Read-out", "7 days or 100 clicks, whichever first")
    text(c, x, y + 8, "Winner is written back to the master brain, not just into the ad account.",
         size=9, color=INK_FAINT)
    return y + 22


# ═══════════════════════════════════════════════════════════════════════════
# 04 — VIDEO STATION
# ═══════════════════════════════════════════════════════════════════════════

def r04_video():
    c = Canvas(1440, 900)

    def draw_stage():
        # vertical reel canvas with safe zones
        checkered(c, 104, 210, 250, 444)
        c.rect(104, 210, 250, 444, fill="#0c150e")
        c.circle(229, 372, 92, fill=PINE)
        c.rect(160, 306, 138, 132, fill="rgba(138,138,122,0.18)", stroke=DIVIDER_MID, dash="5 4")
        text(c, 229, 366, "PRODUCT", size=9.5, color="#a8b3a4", font=MONO, anchor="middle",
             spacing=0.06)
        text(c, 229, 380, "reference-locked", size=8, color="#6a7a66", anchor="middle")
        text(c, 229, 470, "HOOK TEXT", size=15, color="#f5f0e8", font=SERIF, weight=700,
             anchor="middle")
        text(c, 229, 490, "keep above platform UI", size=8.5, color="#b0afa0", anchor="middle")
        # safe zone overlay
        c.rect(104, 210, 250, 444, fill="none", stroke=CLAY, sw=1, opacity=0.5)
        c.rect(112, 246, 234, 372, fill="none", stroke=OCHRE, sw=1, dash="5 4")
        text(c, 112, 240, "SAFE ZONE 9:16", size=7.5, color=OCHRE, font=MONO, spacing=0.06)

        # storyboard
        text(c, 386, 226, "STORYBOARD · 15s · 9:16", size=8.5, color="#a8b3a4", font=MONO,
             spacing=0.06)
        beats = [("0–3s", "HOOK", "product on plain sweep", "Wan · $0.25"),
                 ("3–6s", "PROBLEM", "hand lifts clumped powder", "Kling v3 i2v"),
                 ("6–11s", "SOLUTION", "pour, stir, drink", "Kling v3 i2v"),
                 ("11–15s", "CTA", "packshot + price band", "composited")]
        for i, (t, name, desc, eng) in enumerate(beats):
            x = 386 + i * 135
            c.rect(x, 238, 127, 104, fill="rgba(255,255,255,0.05)",
                   stroke="rgba(255,255,255,0.12)", rx=8)
            text(c, x + 10, 258, t, size=8.5, color=OCHRE, font=MONO)
            text(c, x + 10, 274, name, size=11, color="#f5f0e8", weight=600)
            text(c, x + 10, 292, desc, size=8.5, color="#a8b3a4")
            text(c, x + 10, 306, eng, size=8, color="#6a7a66", font=MONO)
            thumb(c, x + 10, 314, 107, 20, "")
            if i < 3:
                arrow(c, x + 128, 290, x + 136, 290, color="#6a7a66", sw=1.2)

        # url-to-video intake
        text(c, 386, 380, "SOURCE", size=8.5, color="#a8b3a4", font=MONO, spacing=0.06)
        c.rect(386, 390, 540, 30, fill="rgba(255,255,255,0.07)",
               stroke="rgba(255,255,255,0.14)", rx=5)
        text(c, 398, 410, "amazon.com/dp/B0C7QX4M2P  (ASIN + listing only — no purchase, no "
                          "login)", size=9.5, color="#a8b3a4", font=MONO)
        text(c, 386, 446, "Pulled: title, 5 bullets, price, pack count, 4 listing images. "
                          "Not pulled: reviews, seller account, ad reports.", size=9,
             color="#8a9a86")

        # cost bar
        text(c, 386, 484, "COST LEDGER (per render)", size=8.5, color="#a8b3a4", font=MONO,
             spacing=0.06)
        for i, (k, v, col) in enumerate([("Draft beats", "$0.25 × 4", OCHRE),
                                         ("Final cut", "$1.05 × 1", FOREST),
                                         ("Voiceover", "$0.03", SAGE_SOFT)]):
            yy = 496 + i * 26
            c.rect(386, yy, 200, 18, fill="rgba(255,255,255,0.06)", rx=4)
            c.rect(386, yy, 120 - i * 30, 18, fill=col, rx=4)
            text(c, 594, yy + 13, f"{k} — {v}", size=9, color="#a8b3a4")
        text(c, 386, 588, "Video is metered spend. Every render is a named, capped, "
                          "operator-approved job — never an automatic retry.", size=9,
             color="#8a9a86")

    def insp(ix, iy, iw):
        y = iy
        y = section(c, ix, y, iw, "Clip plan", "15s · 9:16",
                    body=lambda yy: _vid_plan(c, ix, yy, iw))
        y = section(c, ix, y, iw, "Voice & script", "brand-bound",
                    body=lambda yy: _vid_script(c, ix, yy, iw))
        y = section(c, ix, y, iw, "Spend guardrail", "capped",
                    body=lambda yy: _vid_spend(c, ix, yy, iw))
        y = section(c, ix, y, iw, "Disclosure", "AI-generated",
                    body=lambda yy: _vid_disclosure(c, ix, yy, iw))

    shell(c, "Video", "Reel · URL-to-video · Set A", "1080×1920", ("storyboard", "unknown"),
          draw_stage, "Video inspector", insp,
          "Video station — URL-to-video, UGC-style clips, and 3D or animated product video, with "
          "the spend ledger visible before a single second is rendered.",
          rail_counts={"Listing": 6, "Ads": 12, "Video": 4, "Social": 9, "Product": 3, "Brand": 1},
          preflight="No clip rendered — this is a storyboard and a cost ledger. Video is metered "
                    "spend and requires a named, capped, operator-approved job.",
          badge_kind="0 rendered")

    footer(c, 852,
           "Render 04 — PROPOSED: Video station. Honest about the repo's real posture: no local "
           "video pipeline exists, and docs/CREATIVE_SOCIAL_LOCAL_STATUS.md lists the video budget "
           "as an unanswered owner decision. This render therefore shows the STORYBOARD and the "
           "COST LEDGER, not a fabricated clip.")
    write(c, "04-video-station.svg", "Proposed — Design Studio video station",
          "Video content-type: 9:16 reel canvas with platform safe-zone overlay, a 4-beat "
          "storyboard with per-beat engine and cost, a URL-to-video intake limited to public "
          "listing data, and a spend ledger with a hard cap.")


def _vid_plan(c, x, y, w):
    for k, v in [("Duration", "15s · 9:16"), ("Beats", "4 · hook → problem → solution → CTA"),
                 ("Source", "amazon.com/dp/B0C7QX4M2P"),
                 ("Aspect set", "9:16 · 1:1 · 16:9")]:
        y = krow(c, x, y, w, k, v)
    return y + 2


def _vid_script(c, x, y, w):
    y = krow(c, x, y, w, "Voice", "Word Coffee — warm, unhurried")
    y = krow(c, x, y, w, "Script", "brand-templated, operator-editable")
    y = krow(c, x, y, w, "Captions", "burned in, term-matched")
    return y + 4


def _vid_spend(c, x, y, w):
    y = krow(c, x, y, w, "Per render", "$1.33 draft + final", tone="warn")
    y = krow(c, x, y, w, "Cap per job", "$25.00", tone="ok")
    y = krow(c, x, y, w, "Approval", "required before first second", tone="warn")
    text(c, x, y + 8, "On any hard failure: stop, persist what succeeded, record a scrubbed "
                      "manifest, report. Never auto-retry.", size=9, color=INK_FAINT)
    return y + 24


def _vid_disclosure(c, x, y, w):
    y = krow(c, x, y, w, "AI disclosure", "burned into first frame")
    y = krow(c, x, y, w, "Watermark", "detected where the provider adds one", tone="ok")
    return y + 4
# ═══════════════════════════════════════════════════════════════════════════
# 05 — SOCIAL STATION
# ═══════════════════════════════════════════════════════════════════════════

def r05_social():
    c = Canvas(1440, 900)

    def draw_stage():
        text(c, 104, 224, "CHANNEL FIT — heuristics, not measured performance", size=8.5,
             color="#a8b3a4", font=MONO, spacing=0.06)
        chans = [("Instagram", "1080×1350", "4:5 · feed"), ("TikTok", "1080×1920", "9:16"),
                 ("YouTube", "1280×720", "16:9 thumb"), ("Pinterest", "1000×1500", "2:3")]
        for i, (n, d, note) in enumerate(chans):
            x = 104 + i * 205
            c.rect(x, 234, 190, 62, fill="rgba(255,255,255,0.05)",
                   stroke="rgba(255,255,255,0.12)", rx=8)
            text(c, x + 12, 254, n, size=10.5, color="#f5f0e8", weight=600)
            text(c, x + 12, 270, d, size=9, color="#a8b3a4", font=MONO)
            text(c, x + 12, 284, note, size=8.5, color="#6a7a66")

        # calendar
        text(c, 104, 330, "CONTENT CALENDAR · OCTOBER 2026", size=8.5, color="#a8b3a4",
             font=MONO, spacing=0.06)
        days = ["M", "T", "W", "T", "F", "S", "S"]
        for i, d in enumerate(days):
            text(c, 104 + i * 103 + 44, 350, d, size=9, color="#6a7a66", anchor="middle")
        plan = {
            2: [("REEL", FOREST)], 4: [("POST", SURFACE_ACTIVE)], 6: [("CAROUSEL", OCHRE)],
            9: [("REEL", FOREST)], 11: [("POST", SURFACE_ACTIVE)], 14: [("CAROUSEL", OCHRE)],
            16: [("REEL", FOREST)], 18: [("POST", SURFACE_ACTIVE)], 21: [("CAROUSEL", OCHRE)],
            23: [("REEL", FOREST)], 26: [("POST", SURFACE_ACTIVE)], 28: [("CAROUSEL", OCHRE)],
        }
        for wk in range(4):
            for d in range(7):
                daynum = wk * 7 + d + 1
                x = 104 + d * 103
                yy = 362 + wk * 62
                c.rect(x, yy, 96, 54, fill="rgba(255,255,255,0.04)",
                       stroke="rgba(255,255,255,0.09)", rx=6)
                text(c, x + 7, yy + 14, str(daynum), size=8, color="#5a6a56", font=MONO)
                for j, (lbl, col) in enumerate(plan.get(daynum, [])):
                    c.rect(x + 7, yy + 22 + j * 14, 66, 12, fill=col, rx=6)
                    text(c, x + 40, yy + 31 + j * 14, lbl, size=7, color="#f5f0e8",
                         weight=700, anchor="middle")

        # carousel composition
        text(c, 104, 636, "CAROUSEL · 5 PANELS", size=8.5, color="#a8b3a4", font=MONO,
             spacing=0.06)
        for i, (lbl, note) in enumerate([("1 · HOOK", "term-matched"),
                                         ("2 · PROBLEM", "clumping"),
                                         ("3 · PROOF", "in-use shot"),
                                         ("4 · PRODUCT", "reference-locked"),
                                         ("5 · CTA", "offer badge")]):
            thumb(c, 104 + i * 160, 648, 150, 118, lbl, note)

    def insp(ix, iy, iw):
        y = iy
        y = section(c, ix, y, iw, "Post record", "Draft → Ready",
                    body=lambda yy: _soc_post(c, ix, yy, iw))
        y = section(c, ix, y, iw, "Publishing boundary", "not connected",
                    body=lambda yy: _soc_publish(c, ix, yy, iw))
        y = section(c, ix, y, iw, "Voice preset", "Word Coffee",
                    body=lambda yy: _soc_voice(c, ix, yy, iw))
        y = section(c, ix, y, iw, "Handoff", "to the master brain",
                    body=lambda yy: _soc_handoff(c, ix, yy, iw))

    shell(c, "Social", "Carousel · 5 panels · IG + TT", "1080×1350", ("draft", "unknown"),
          draw_stage, "Social inspector", insp,
          "Social station — reels, posts, carousels and a content calendar. Channel-fit guidance is "
          "labelled heuristic, because no social analytics provider is connected.",
          rail_counts={"Listing": 6, "Ads": 12, "Video": 4, "Social": 9, "Product": 3, "Brand": 1},
          preflight="No publishing, no scheduling, no analytics — no social OAuth or provider "
                    "exists in this build. Records are real local workflow state only.",
          badge_kind="no publisher")

    footer(c, 852,
           "Render 05 — PROPOSED: Social station. Keeps the honest boundary the current SocialPulse "
           "room already enforces (no OAuth, no publisher, no analytics — reach and engagement read "
           "UNKNOWN) while adding the term-matched carousel panels and the handoff back into the "
           "master brain.")
    write(c, "05-social-station.svg", "Proposed — Design Studio social station",
          "Social content-type: channel-fit strip labelled heuristic, an October content calendar, "
          "a 5-panel carousel composition, and an inspector with the publishing boundary stated "
          "plainly.")


def _soc_post(c, x, y, w):
    for k, v in [("Record", "POST-1042"), ("State", "Draft → In Review"),
                 ("Channels", "Instagram, TikTok"), ("Panels", "5 · term-matched")]:
        y = krow(c, x, y, w, k, v)
    return y + 2


def _soc_publish(c, x, y, w):
    y = check(c, x, y, w, False, "No social OAuth or publisher connected",
              "records are local workflow state, never a publish")
    y = check(c, x, y, w, False, "No analytics provider — reach / engagement read UNKNOWN")
    text(c, x, y + 8, "Approval here is an internal review state, never publishing "
                      "authorization.", size=9, color=INK_FAINT)
    return y + 22


def _soc_voice(c, x, y, w):
    for k, v in [("Kit", "Word Coffee"), ("Tone", "warm, unhurried, craft-led"),
                 ("Hashtags", "10 per post · 3 drawn from bound terms")]:
        y = krow(c, x, y, w, k, v)
    return y + 4


def _soc_handoff(c, x, y, w):
    y = krow(c, x, y, w, "Output", "bundle manifest · references only")
    y = krow(c, x, y, w, "Learning", "term → post pairing written back")
    return y + 4


# ═══════════════════════════════════════════════════════════════════════════
# 06 — PRODUCT & PACKAGING STATION
# ═══════════════════════════════════════════════════════════════════════════

def r06_packaging():
    c = Canvas(1440, 900)

    def draw_stage():
        # 3D-ish box on the dark pane, drawn with the real renderer's approach
        c.rect(104, 214, 330, 330, fill="rgba(255,255,255,0.04)",
               stroke="rgba(255,255,255,0.1)", rx=12)
        # floor
        c.rect(104, 470, 330, 74, fill="rgba(0,0,0,0.25)")
        # box — isometric-ish three faces
        ox, oy, bw, bh, dep = 200, 300, 130, 150, 44
        c.path(f"M {ox} {oy} L {ox+bw} {oy} L {ox+bw+dep} {oy-dep} L {ox+dep} {oy-dep} Z",
               fill="#f2ede5", stroke="rgba(26,26,26,0.25)")
        c.path(f"M {ox+bw} {oy} L {ox+bw+dep} {oy-dep} L {ox+bw+dep} {oy+bh-dep} "
               f"L {ox+bw} {oy+bh} Z", fill="#e8e2d8", stroke="rgba(26,26,26,0.25)")
        c.path(f"M {ox} {oy} L {ox+bw} {oy} L {ox+bw} {oy+bh} L {ox} {oy+bh} Z",
               fill="#f5f0e8", stroke="rgba(26,46,26,0.28)")
        # front face artwork — honest placeholder
        c.rect(ox + 12, oy + 16, bw - 24, 60, fill="rgba(138,138,122,0.12)",
               stroke=DIVIDER_MID, dash="4 3")
        text(c, ox + bw / 2, oy + 44, "FRONT ART", size=8, color=INK_SOFT, font=MONO,
             anchor="middle")
        text(c, ox + bw / 2, oy + 58, "operator's own file", size=7.5, color=INK_FAINT,
             anchor="middle")
        text(c, ox + bw / 2, oy + 96, "WORD COFFEE", size=11, color=PINE_DEEP, font=SERIF,
             weight=700, anchor="middle")
        text(c, ox + bw / 2, oy + 110, "cold brew concentrate", size=8, color=INK_MID,
             anchor="middle")
        c.rect(ox + 30, oy + 126, 70, 14, fill=OCHRE, rx=7)
        text(c, ox + 65, oy + 136, "12 CT", size=7.5, color="#ffffff", weight=700,
             anchor="middle")
        # contact shadow
        import math as _m
        c.add(f'<ellipse cx="{ox + bw/2 + dep/2}" cy="{oy + bh + 8}" rx="{bw*0.55}" '
              f'ry="9" fill="rgba(20,26,20,0.34)"/>')
        # camera bar
        cams = [("Hero 3/4", "yaw −28°"), ("Front on", "yaw 0°"), ("Top down", "pitch 62°"),
                ("Profile", "yaw −90°")]
        for i, (n, d) in enumerate(cams):
            x = 104 + i * 84
            c.rect(x, 558, 78, 28, fill="rgba(255,255,255,0.06)",
                   stroke="rgba(255,255,255,0.12)", rx=6)
            text(c, x + 39, 570, n, size=8.5, color="#d9d3c6", anchor="middle")
            text(c, x + 39, 582, d, size=7.5, color="#8a9a86", anchor="middle", font=MONO)

        # dieline panel
        text(c, 456, 230, "DIELINE · PRODUCTION SPEC", size=8.5, color="#a8b3a4", font=MONO,
             spacing=0.06)
        c.rect(456, 242, 200, 240, fill="#f7f5f0", stroke=DIVIDER_MID, rx=3)
        c.rect(466, 252, 180, 220, fill="none", stroke=CLAY, sw=0.8, dash="6 4")
        for i in range(1, 4):
            line(c, 466, 252 + i * 55, 646, 252 + i * 55, stroke=CLAY, sw=0.6, dash="3 4")
        for i in range(1, 3):
            line(c, 466 + i * 90, 252, 466 + i * 90, 472, stroke=CLAY, sw=0.6, dash="3 4")
        text(c, 556, 528, "bleed 0.125in · safe 0.25in", size=8, color=CLAY, font=MONO,
             anchor="middle")
        for i, (lbl, note) in enumerate([("INSERT CARD", "thank-you + QR"),
                                         ("LABEL PROOF", "jar · wrap"),
                                         ("MAILER", "shipping box"),
                                         ("SLEEVE", "gift band")]):
            thumb(c, 456 + i * 118, 552, 108, 78, lbl, note)

        # export checklist
        text(c, 456, 662, "MANUFACTURER HANDOFF", size=8.5, color="#a8b3a4", font=MONO,
             spacing=0.06)
        c.rect(456, 674, 468, 66, fill="rgba(255,255,255,0.04)",
               stroke="rgba(255,255,255,0.1)", rx=8)
        for i, t in enumerate(["PDF/X-1a · CMYK", "dieline + art in one file",
                               "bleed and safe marked", "no flattened transparency"]):
            text(c, 470, 692 + (i % 2) * 20, ("✓ " if i < 3 else "○ ") + t, size=9,
                 color="#a8b3a4" if i < 3 else "#8a9a86")
            if i % 2 == 1:
                pass

    def insp(ix, iy, iw):
        y = iy
        y = section(c, ix, y, iw, "Pack geometry", "carton",
                    body=lambda yy: _pk_geo(c, ix, yy, iw))
        y = section(c, ix, y, iw, "Face artwork", "front mapped",
                    body=lambda yy: _pk_faces(c, ix, yy, iw))
        y = section(c, ix, y, iw, "Print readiness", "1 open item",
                    body=lambda yy: _pk_print(c, ix, yy, iw))

    shell(c, "Product", "Packaging concept · carton", "1.0 × 1.35 × 0.28", ("concept", "unknown"),
          draw_stage, "Packaging inspector", insp,
          "Product and packaging station — concepts, mockups, dielines, insert cards and "
          "manufacturer-ready specs. Geometry is honest: a real mesh with the operator's own art "
          "mapped per face, never a photoreal render.",
          rail_counts={"Listing": 6, "Ads": 12, "Video": 4, "Social": 9, "Product": 3, "Brand": 1},
          preflight="Dieline complete · CMYK PDF/X-1a · bleed and safe marked · one open item: "
                    "flatten transparency before export",
          badge_kind="1 open item")

    footer(c, 852,
           "Render 06 — PROPOSED: Product & packaging station. The 3D renderer already exists and "
           "is dependency-free (northstar-os-ui/src/studio/engine/three.js, a real mesh with painter's "
           "algorithm on a Canvas 2D context, no WebGL and no three.js). What is NEW: the print-spec "
           "export and the manufacturer handoff checklist.")
    write(c, "06-packaging-station.svg", "Proposed — Design Studio product and packaging station",
          "Packaging content-type: three-face box preview with the operator's own front artwork "
          "mapped, camera presets, a dieline with bleed and safe marked, and a print-readiness "
          "checklist.")


def _pk_geo(c, x, y, w):
    for k, v in [("Preset", "Carton · 3 visible faces"), ("Size", "1.0 × 1.35 × 0.28"),
                 ("Camera", "Hero 3/4 · yaw −28°, pitch 12°"),
                 ("Lighting", "Softbox · catalogue safe")]:
        y = krow(c, x, y, w, k, v, mono=True)
    text(c, x, y + 8, "Honest geometry: a real mesh shaded with a three-point rig. It is not a "
                      "photoreal render and is never labelled as one.", size=9, color=INK_FAINT)
    return y + 24


def _pk_faces(c, x, y, w):
    for k, v in [("Front", "front-art-v3.png · mapped"), ("Right", "side panel · mapped"),
                 ("Top", "lid band · mapped"),
                 ("Back / bottom", "not mapped")]:
        y = krow(c, x, y, w, k, v, tone="warn" if "not" in v else None)
    return y + 4


def _pk_print(c, x, y, w):
    y = check(c, x, y, w, True, "Dieline drawn", "cut, fold, bleed, safe all marked")
    y = check(c, x, y, w, True, "Colour space", "CMYK · PDF/X-1a")
    y = check(c, x, y, w, True, "Resolution", "≥300 dpi at final size")
    y = check(c, x, y, w, False, "Transparency", "flatten before export")
    return y + 4
# ═══════════════════════════════════════════════════════════════════════════
# 07 — BRAND SYSTEM STATION
# ═══════════════════════════════════════════════════════════════════════════

def r07_brand():
    c = Canvas(1440, 900)

    def draw_stage():
        text(c, 104, 224, "BRAND KIT · WORD COFFEE", size=8.5, color="#a8b3a4", font=MONO,
             spacing=0.06)
        # palette
        text(c, 104, 250, "PALETTE", size=8, color="#8a9a86", font=MONO, spacing=0.06)
        pal = [("#f7f2ea", "paper"), ("#2b1d16", "ink"), ("#7a4a2b", "roast"),
               ("#c9a227", "accent"), ("#e0d3bd", "bone")]
        for i, (hexc, name) in enumerate(pal):
            x = 104 + i * 78
            c.rect(x, 260, 66, 66, fill=hexc,
                   stroke="rgba(255,255,255,0.2)" if i == 1 else "rgba(255,255,255,0.1)", rx=8)
            text(c, x + 33, 342, name, size=8.5, color="#cfd6ca", anchor="middle")
            text(c, x + 33, 354, hexc, size=7.5, color="#6a7a66", anchor="middle", font=MONO)

        # typography specimen
        text(c, 500, 250, "TYPE", size=8, color="#8a9a86", font=MONO, spacing=0.06)
        c.rect(500, 260, 424, 100, fill="rgba(255,255,255,0.04)",
               stroke="rgba(255,255,255,0.1)", rx=8)
        text(c, 518, 292, "Cold-brew in 30 seconds", size=17, color="#f5f0e8", font=SERIF,
             weight=700)
        text(c, 518, 314, "Libre Baskerville · heading · editorial moments only", size=8.5,
             color="#8a9a86")
        text(c, 518, 338, "DM Sans · body and UI · always legible at thumbnail size", size=10,
             color="#cfd6ca")
        text(c, 518, 352, "JetBrains Mono · dimensions, specs, ids", size=9, color="#a8b3a4",
             font=MONO)

        # voice
        text(c, 104, 396, "VOICE", size=8, color="#8a9a86", font=MONO, spacing=0.06)
        c.rect(104, 406, 380, 84, fill="rgba(255,255,255,0.04)",
               stroke="rgba(255,255,255,0.1)", rx=8)
        text(c, 120, 430, "Warm, unhurried, craft-led.", size=13, color="#f5f0e8", font=SERIF,
             weight=600)
        for i, t in enumerate(["Short sentences. Concrete nouns.", "No urgency language.",
                               "Never a claim we cannot show."]):
            text(c, 120, 452 + i * 15, "· " + t, size=9.5, color="#a8b3a4")

        # claims library
        text(c, 500, 396, "CLAIMS LIBRARY", size=8, color="#8a9a86", font=MONO, spacing=0.06)
        rows = [("slow-roasted in small batches", "approved", "supported by own process doc"),
                ("no fillers, no added sugar", "approved", "matches label"),
                ("clinically proven", "blocked", "no evidence attached"),
                ("#1 best seller", "blocked", "prohibited claim form"),
                ("doctor recommended", "blocked", "needs licensure evidence")]
        for i, (claim, st, note) in enumerate(rows):
            yy = 406 + i * 17
            col = FOREST if st == "approved" else CLAY
            text(c, 500, yy + 11, claim, size=9.5, color="#d9d3c6")
            c.rect(500 + 210, yy + 3, 46, 11, fill=col, rx=5.5)
            text(c, 523, yy + 11, st.upper(), size=6.5, color="#ffffff", weight=700,
                 anchor="middle")
            text(c, 500 + 266, yy + 11, note, size=8, color="#6a7a66")

        # kit inheritance
        text(c, 104, 520, "KIT INHERITANCE", size=8, color="#8a9a86", font=MONO, spacing=0.06)
        assets = [("MAIN IMAGE", "paper + ink"), ("A+ BANNER", "roast accent"),
                  ("REEL COVER", "deep pine"), ("INSERT CARD", "bone + ochre")]
        for i, (a, k) in enumerate(assets):
            x = 104 + i * 205
            c.rect(x, 530, 190, 56, fill="rgba(255,255,255,0.04)",
                   stroke="rgba(255,255,255,0.1)", rx=8)
            text(c, x + 12, 548, a, size=9, color="#cfd6ca", weight=600)
            text(c, x + 12, 564, k, size=8.5, color="#6a7a66", font=MONO)
            text(c, x + 12, 578, "inherits kit automatically", size=7.5, color="#5a6a56")

        # prohibited language
        text(c, 104, 616, "PROHIBITED & APPROVED LANGUAGE — enforced at compose time, not at "
                          "export", size=8.5, color="#a8b3a4", font=MONO, spacing=0.06)
        for i, (n, d, col) in enumerate([("31", "blocked phrases", CLAY),
                                         ("12", "approved phrases", FOREST),
                                         ("8", "need-evidence phrases", OCHRE)]):
            x = 104 + i * 205
            c.rect(x, 628, 190, 62, fill="rgba(255,255,255,0.04)",
                   stroke="rgba(255,255,255,0.1)", rx=8)
            text(c, x + 14, 660, n, size=20, color=col, font=SERIF, weight=700)
            text(c, x + 62, 660, d, size=9, color="#a8b3a4")

    def insp(ix, iy, iw):
        y = iy
        y = section(c, ix, y, iw, "Active kit", "Word Coffee",
                    body=lambda yy: _br_kit(c, ix, yy, iw))
        y = section(c, ix, y, iw, "Claims rule set", "31 blocked",
                    body=lambda yy: _br_claims(c, ix, yy, iw))
        y = section(c, ix, y, iw, "Evidence ledger", "2 sources",
                    body=lambda yy: _br_evidence(c, ix, yy, iw))

    shell(c, "Brand", "Brand system · Word Coffee", "kit + claims", ("2 kits", "unknown"),
          draw_stage, "Brand inspector", insp,
          "Brand system station — kit, voice, claims library, and approved / prohibited language. "
          "The guardrail fires at compose time, so an unsupported claim never reaches a canvas.",
          rail_counts={"Listing": 6, "Ads": 12, "Video": 4, "Social": 9, "Product": 3, "Brand": 1},
          preflight="Kit applied to 19 of 19 assets · 1 claim blocked at compose time · "
                    "evidence ledger: 2 sources attached",
          badge_kind="1 blocked")

    footer(c, 852,
           "Render 07 — PROPOSED: Brand system station. Brand voice ALREADY EXISTS in the repo "
           "(Northstar_backend/social_pulse.py load_brand_voice() with tone / style / "
           "hashtags_per_post / emoji_usage / call_to_action, and listing_forge.py's brand_voice "
           "dict threaded into every prompt builder). What is NEW: the claims library, the "
           "evidence ledger, and enforcement at compose time rather than at export.")
    write(c, "07-brand-system.svg", "Proposed — Design Studio brand system station",
          "Brand content-type: palette and type specimen drawn on the dark pane, voice statement, "
          "a claims library with approved and blocked phrases and the reason for each, kit "
          "inheritance previews, and an evidence ledger.")


def _br_kit(c, x, y, w):
    for k, v in [("Kit", "Word Coffee · from a local work brief"),
                 ("Palette", "5 hexes · ink and accent bound"),
                 ("Fonts", "Libre Baskerville / DM Sans"),
                 ("Voice", "warm, unhurried, craft-led")]:
        y = krow(c, x, y, w, k, v)
    return y + 2


def _br_claims(c, x, y, w):
    y = krow(c, x, y, w, "Blocked", "31 phrases", tone="error")
    y = krow(c, x, y, w, "Approved", "12 phrases", tone="ok")
    y = krow(c, x, y, w, "Needs evidence", "8 phrases", tone="warn")
    text(c, x, y + 8, "A blocked phrase cannot be typed into a text layer. It is not a warning at "
                      "export — the layer will not accept it.", size=9, color=INK_FAINT)
    return y + 24


def _br_evidence(c, x, y, w):
    y = krow(c, x, y, w, "Claim: small batch", "process doc v2 · attached", tone="ok")
    y = krow(c, x, y, w, "Claim: no added sugar", "label spec · attached", tone="ok")
    y = krow(c, x, y, w, "Claim: clinically proven", "no source · blocked", tone="error")
    return y + 4


# ═══════════════════════════════════════════════════════════════════════════
# 08 — THE LEARNING LOOP
# ═══════════════════════════════════════════════════════════════════════════

def r08_loop():
    c = Canvas(1440, 1080)
    topnav(c, active="Design Studio")
    text(c, 28, 100, "Design Studio", size=26, color=PINE_DEEP, font=SERIF, weight=700)
    text(c, 28, 122, "The closed loop — search terms become creative briefs, assets become "
                     "variants, and results are written back to the master brain.", size=12,
         color=INK_MID)

    steps = [
        ("1", "SEARCH TERMS", "Amazon Ads search-term report\nkeyword_performance table",
         "searchTerm · impressions · clicks\nspend · orders · sales · acos", FOREST),
        ("2", "CREATIVE BRIEF", "term → asset mapping\nbrief inherits the winning terms",
         "brief carries: term, tier,\nhistorical orders", PINE),
        ("3", "ASSET VARIANTS", "compose against the brief\non-image copy matches the term",
         "N variants · one master doc\nreference-locked product", PINE_LIGHT),
        ("4", "PRE-FLIGHT", "Amazon rules + claims guardrail\nlisting-to-ad consistency",
         "blockers must be cleared\nbefore export", OCHRE),
        ("5", "PUBLISH / TEST", "listing upload or ad set\nA/B in the experiment slot",
         "experiment read-out at\n7 days or 100 clicks", CLAY),
        ("6", "PERFORMANCE", "impressions, clicks, orders\nper variant per term",
         "measured, not inferred", SAGE := "#5a7a5a"),
        ("7", "LEARNING", "written back to the master brain\nwinning pairings are reused",
         "revision + unlearn supported\nlocal, free, no live calls", PINE),
    ]

    x0, y0 = 28, 168
    bw, bh = 180, 132
    gap = 12
    for i, (n, title, l1, l2, col) in enumerate(steps):
        x = x0 + (i % 4) * (bw + gap)
        y = y0 + (i // 4) * (bh + 64)
        c.rect(x, y, bw, bh, fill=SURFACE, stroke=DIVIDER, rx=12)
        c.rect(x, y, bw, 26, fill=col, rx=12)
        c.rect(x, y + 14, bw, 12, fill=col)
        text(c, x + 12, y + 18, f"{n} · {title}", size=9.5, color="#ffffff", weight=700,
             spacing=0.05)
        text(c, x + 12, y + 46, l1, size=9, color=INK)
        text(c, x + 12, y + 78, l2, size=8, color=INK_FAINT, font=MONO)
        if i < len(steps) - 1:
            if i % 4 < 3:
                arrow(c, x + bw + 1, y + bh / 2, x + bw + gap - 2, y + bh / 2, color=FOREST)
            else:
                arrow(c, x + bw / 2, y + bh + 2, x + bw / 2, y + bh + 30, color=FOREST)
                arrow(c, x + bw / 2, y + bh + 30, x0 + (3 - 0) * (bw + gap) + bw / 2,
                      y + bh + 30, color=FOREST)

    # feedback arrow back to 1
    ly = y0 + 2 * (bh + 64) - 44
    arrow(c, x0 + 3 * (bw + gap) + bw / 2, y0 + bh + 64 + 2, x0 + 3 * (bw + gap) + bw / 2, ly,
          color=OCHRE, dash="6 4")
    arrow(c, x0 + 3 * (bw + gap) + bw / 2, ly, x0 + bw / 2, ly, color=OCHRE, dash="6 4")
    arrow(c, x0 + bw / 2, ly, x0 + bw / 2, y0 - 4, color=OCHRE, dash="6 4")
    pill(c, x0 + bw + 200, ly - 22, "learning loop closes here", "ochre", size=9)

    # data contracts
    dy = y0 + 2 * (bh + 64) + 22
    px, py = card(c, 28, dy, 1384, 148, pad=18)
    text(c, px, py, "What the loop needs — already in the repo", size=15, color=PINE_DEEP,
         font=SERIF, weight=600)
    cols = [
        ("BRAND VOICE", "social_pulse.load_brand_voice()", "tone · style · hashtags · emoji · CTA"),
        ("KEYWORD TIERS", "ad_pilot.classify_keyword_tier()", "tier + negative candidates"),
        ("SEARCH-TERM DATA", "ads_api_importer.run_search_term_report()",
         "searchTerm · clicks · orders · sales"),
        ("ORG SCOPING", "foundation.repositories.for_keyword()", "org_id + keyword_id access"),
    ]
    cw2 = (1384 - 36) / 4
    for i, (k, f, d) in enumerate(cols):
        x = px + i * cw2
        text(c, x, py + 32, k, size=8.5, color=INK_SOFT, weight=700, spacing=0.05)
        text(c, x, py + 50, f, size=9.5, color=FOREST, font=MONO)
        text(c, x, py + 70, d, size=9, color=INK_FAINT, font=MONO)
        if i:
            line(c, x - 14, py + 18, x - 14, py + 74, stroke=DIVIDER)
    text(c, px, py + 104, "All four exist as code today. The loop needs no new backend data "
                          "source — it needs the Design Studio to read them and write back.",
         size=10, color=INK_MID)

    footer(c, 1000,
           "Render 08 — the loop. The data contracts named here are real repo symbols, verified by "
           "code read. The measurement link (6) is the only one that depends on a connected ad or "
           "listing data source; until then it reads UNKNOWN rather than a placeholder.")
    write(c, "08-learning-loop.svg", "Proposed — the closed learning loop",
          "Seven steps from Amazon search terms through creative briefs, asset variants, "
          "pre-flight, publishing and testing, performance measurement, and learning written back "
          "to the master brain — with the four repo data contracts each step depends on.")
# ═══════════════════════════════════════════════════════════════════════════
# 09 — THE COMPARISON
# ═══════════════════════════════════════════════════════════════════════════

def r09_comparison():
    c = Canvas(1600, 1120)
    topnav(c, w=1600, active="Design Studio")
    text(c, 28, 100, "Before / after — how the Design Studio differs", size=26, color=PINE_DEEP,
         font=SERIF, weight=700)
    text(c, 28, 122, "Left: today's /creative-studio. Right: the proposed Design Studio. "
                     "Same paper-and-pine identity; the difference is what sits in the middle.",
         size=12, color=INK_MID)

    # ── left: today ──
    c.rect(28, 150, 748, 592, fill=SURFACE, stroke=DIVIDER, rx=12)
    c.rect(28, 150, 748, 32, fill=SURFACE_RAISED, rx=12)
    c.rect(28, 166, 748, 16, fill=SURFACE_RAISED)
    text(c, 44, 171, "TODAY · /creative-studio", size=10.5, color=INK_MID, weight=700,
         spacing=0.04)
    pill(c, 660, 156, "concept", "unknown", size=8.5, h=16)
    for i, t in enumerate(["Briefs", "Image Composer", "Video / Shorts", "Production Queue",
                           "Variants & History", "Assets", "Exports", "Library"]):
        x = 44 + i * 90
        c.rect(x, 192, 86, 24, fill=SURFACE_RAISED if i else FOREST_GLOW,
               stroke=FOREST if i == 0 else DIVIDER, rx=5)
        text(c, x + 43, 208, t.split(" ")[0], size=8.5, color=FOREST if i == 0 else INK_MID,
             anchor="middle", weight=600 if i == 0 else 400)
    thumb(c, 44, 232, 700, 168, "NO DESIGN SURFACE",
          "no canvas · no layers · no format presets · every preview is a placeholder")
    for i, (k, v, col) in enumerate([
            ("Content-type selector", "none — 8 flat tabs", CLAY),
            ("Format knowledge", "5 aspects, 5 sizes, 5 formats", CLAY),
            ("Brand kit", "a 4-item string list", CLAY),
            ("Amazon compliance", "absent", CLAY),
            ("Keyword binding", "absent", CLAY),
            ("Performance loop", "absent", CLAY),
            ("Design engine", "exists but is orphaned", OCHRE)]):
        y = 418 + i * 42
        c.rect(44, y, 700, 34, fill=SURFACE_RAISED, stroke=DIVIDER, rx=6)
        text(c, 58, y + 22, k, size=10.5, color=INK, weight=500)
        text(c, 730, y + 22, v, size=10, color=col, anchor="end", font=MONO)

    # ── right: proposed ──
    c.rect(824, 150, 748, 592, fill=SURFACE, stroke=FOREST, rx=12)
    c.rect(824, 150, 748, 32, fill=FOREST_GLOW, rx=12)
    c.rect(824, 166, 748, 16, fill=FOREST_GLOW)
    text(c, 840, 171, "PROPOSED · DESIGN STUDIO", size=10.5, color=PINE_DEEP, weight=700,
         spacing=0.04)
    pill(c, 1456, 156, "armed", "forest", size=8.5, h=16)
    for i, (l, n) in enumerate([("Listing", "main · A+"), ("Ads", "SB · SD · SP"),
                                ("Video", "url · UGC"), ("Social", "posts"),
                                ("Product", "dieline"), ("Brand", "claims")]):
        x = 840 + i * 120
        on = i == 0
        c.rect(x, 192, 112, 34, fill=FOREST_GLOW if on else SURFACE_RAISED,
               stroke=FOREST if on else DIVIDER, rx=6)
        ic(c, x + 16, 209, ["layers", "bolt", "video", "calendar", "cube", "palette"][i],
           FOREST if on else INK_SOFT, 12)
        text(c, x + 30, 205, l, size=9.5, color=PINE_DEEP if on else INK_MID, weight=600)
        text(c, x + 30, 218, n, size=7.5, color=INK_FAINT)
    # mini stage
    c.rect(840, 240, 340, 160, fill="#1b2a1c", rx=8)
    text(c, 856, 258, "1600×1600", size=8.5, color="#a8b3a4", font=MONO)
    checkered(c, 856, 268, 308, 118)
    c.rect(856, 268, 308, 118, fill=SURFACE, stroke=DIVIDER_MID)
    text(c, 1010, 322, "PRODUCT COMPOSITE", size=9, color=INK_SOFT, font=MONO, anchor="middle")
    text(c, 1010, 338, "reference-locked", size=8, color=INK_FAINT, anchor="middle")
    # mini inspector
    c.rect(1192, 240, 352, 160, fill=SURFACE_RAISED, stroke=DIVIDER, rx=8)
    for i, (k, v, col) in enumerate([("Pre-flight", "1 BLOCKER", CLAY),
                                     ("Bound terms", "3", FOREST),
                                     ("Claims", "1 flagged", STATUS_WARN)]):
        y = 258 + i * 30
        text(c, 1206, y + 12, k, size=9.5, color=INK_SOFT)
        text(c, 1528, y + 12, v, size=9.5, color=col, anchor="end", font=MONO)
        line(c, 1206, y + 18, 1528, y + 18, stroke=DIVIDER)
    for i, (k, v, col) in enumerate([
            ("Content-type selector", "6 stations · drives everything downstream", FOREST),
            ("Format knowledge", "21 raster specs in 4 families", FOREST),
            ("Brand kit", "palette + type + voice + claims", FOREST),
            ("Amazon compliance", "pre-flight before export", FOREST),
            ("Keyword binding", "assets bound to search terms", FOREST),
            ("Performance loop", "results written to the master brain", FOREST),
            ("Design engine", "mounted and extended", FOREST)]):
        y = 418 + i * 42
        c.rect(840, y, 704, 34, fill=SURFACE_RAISED, stroke=DIVIDER, rx=6)
        text(c, 854, y + 22, k, size=10.5, color=INK, weight=500)
        text(c, 1530, y + 22, v, size=9.5, color=col, anchor="end")

    # verdict band
    vy = 762
    px, py = card(c, 28, vy, 1544, 300, pad=22)
    text(c, px, py + 4, "What actually changes", size=17, color=PINE_DEEP, font=SERIF,
         weight=700)
    items = [
        ("The engine gets mounted",
         "northstar-os-ui/src/studio/** already renders documents, formats, mockups and 3D "
         "packaging on a dependency-free Canvas 2D path. It is uncommitted and imported by "
         "nothing."),
        ("One content-type selector replaces eight flat tabs",
         "Formats, templates, compliance rules and brief fields are all derived from the "
         "selected content type, so a listing image and a Sponsored Brands banner can no longer "
         "drift apart."),
        ("Compliance moves from absent to pre-flight",
         "Amazon image and ad rules become a blocking check inside the compose flow, alongside a "
         "claims guardrail that refuses unsupported claims at compose time."),
        ("Creatives become bound to search terms",
         "Each asset carries the term it targets and the ad data behind it, which is what makes "
         "the learning loop possible at all."),
        ("Nothing is fabricated",
         "Product composites stay the operator's own photography, reference-locked across panels. "
         "Blocked, unknown and provider-required states stay visible, exactly as they are today."),
    ]
    for i, (h, b) in enumerate(items):
        y = py + 36 + i * 48
        ic(c, px + 8, y + 6, "check", FOREST, 13)
        text(c, px + 26, y + 10, h, size=12, color=PINE_DEEP, weight=600)
        text(c, px + 26, y + 26, b, size=10, color=INK_MID)

    footer(c, 1090, "Render 09 — the comparison. Left column reconstructed from the shipped "
                    "CreativeStudio.jsx; right column is the proposed Design Studio. No competitor "
                    "design is copied or embedded; every pattern here is the repo's own.")
    write(c, "09-comparison.svg", "Before and after comparison",
          "Side-by-side of today's /creative-studio room and the proposed Design Studio, with a "
          "verdict band listing the five substantive changes.")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    r00_current()
    r02_listing()
    r03_ads()
    r04_video()
    r05_social()
    r06_packaging()
    r07_brand()
    r08_loop()
    r09_comparison()
    print(f"\nAll renders written to {OUT}")


if __name__ == "__main__":
    main()





