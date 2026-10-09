"""SVG mockup toolkit for the NorthstarOS Design Studio renders.

Every primitive is drawn with the real tokens from
``northstar-os-ui/src/styles/tokens.css`` so a render and the shipped room cannot
drift apart. No network, no images, no fonts beyond the two families the design
system already declares.
"""
from __future__ import annotations

import html
import math
from dataclasses import dataclass, field

# ── DESIGN TOKENS (verbatim from src/styles/tokens.css) ──────────────────────
PAPER = "#f5f0e8"
PAPER_WARM = "#f0ebe1"
BONE = "#e8e2d8"
BONE_LIGHT = "#f2ede5"
SURFACE = "#ffffff"
SURFACE_RAISED = "#faf8f4"
SURFACE_HOVER = "#f3efe7"
SURFACE_ACTIVE = "#ece6da"

PINE_DEEP = "#1a2e1a"
PINE = "#1d4a1d"
PINE_MID = "#2d5a2d"
PINE_LIGHT = "#4a7a4a"
INK = "#1a1a1a"
INK_MID = "#5a5a4a"
INK_SOFT = "#8a8a7a"
INK_FAINT = "#b0afa0"

FOREST = "#1d5a1d"
FOREST_GLOW = "rgba(29,90,29,0.15)"
OCHRE = "#c4941a"
OCHRE_SOFT = "rgba(196,148,26,0.12)"
CLAY = "#a04020"
CLAY_SOFT = "rgba(160,64,32,0.12)"
SAGE = "#5a7a5a"
SAGE_SOFT = "rgba(90,122,90,0.12)"

STATUS_OK = "#2d6a2d"
STATUS_OK_SOFT = "rgba(45,106,45,0.12)"
STATUS_WARN = "#b8860b"
STATUS_WARN_SOFT = "rgba(184,134,11,0.12)"
STATUS_ERROR = "#a04020"
STATUS_UNKNOWN = "#8a8a7a"
STATUS_UNKNOWN_SOFT = "rgba(138,138,122,0.12)"

DIVIDER = "rgba(26,46,26,0.08)"
DIVIDER_MID = "rgba(26,46,26,0.14)"
DIVIDER_STRONG = "rgba(26,46,26,0.22)"

SERIF = "Libre Baskerville, Georgia, 'Times New Roman', serif"
UI = "'DM Sans', system-ui, -apple-system, 'Segoe UI', sans-serif"
MONO = "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace"

R = 8          # --radius
R_SM = 5       # --radius-sm
R_LG = 12      # --radius-lg


def esc(s) -> str:
    return html.escape(str(s), quote=True)


@dataclass
class Canvas:
    w: int = 1440
    h: int = 900
    parts: list = field(default_factory=list)

    def add(self, s: str) -> None:
        self.parts.append(s)

    def rect(self, x, y, w, h, fill="none", stroke=None, sw=1, rx=0, opacity=None,
             dash=None, cls=None):
        a = [f'x="{x:.2f}"', f'y="{y:.2f}"', f'width="{max(0, w):.2f}"', f'height="{max(0, h):.2f}"']
        if rx:
            a.append(f'rx="{rx}"')
        if fill != "none":
            a.append(f'fill="{fill}"')
        else:
            a.append('fill="none"')
        if stroke:
            a.append(f'stroke="{stroke}"')
            a.append(f'stroke-width="{sw}"')
        if opacity is not None:
            a.append(f'opacity="{opacity}"')
        if dash:
            a.append(f'stroke-dasharray="{dash}"')
        if cls:
            a.append(f'class="{cls}"')
        self.add("<rect " + " ".join(a) + "/>")

    def text(self, x, y, s, size=12, color=INK_MID, font=UI, weight=400, anchor="start",
             spacing=None, italic=False, opacity=None, family=None, baseline=None):
        a = [f'x="{x:.2f}"', f'y="{y:.2f}"', f'font-family="{font}"', f'font-size="{size}"',
             f'font-weight="{weight}"', f'fill="{color}"']
        if anchor != "start":
            a.append(f'text-anchor="{anchor}"')
        if baseline and baseline != "alphabetic":
            a.append(f'dominant-baseline="{baseline}"')
        if spacing:
            a.append(f'letter-spacing="{spacing}"')
        if italic:
            a.append("font-style=\"italic\"")
        if opacity is not None:
            a.append(f'opacity="{opacity}"')
        self.add("<text " + " ".join(a) + ">" + esc(s) + "</text>")

    def line(self, x1, y1, x2, y2, stroke=DIVIDER_MID, sw=1, dash=None, cap="butt"):
        a = [f'x1="{x1:.2f}"', f'y1="{y1:.2f}"', f'x2="{x2:.2f}"', f'y2="{y2:.2f}"',
             f'stroke="{stroke}"', f'stroke-width="{sw}"', f'stroke-linecap="{cap}"']
        if dash:
            a.append(f'stroke-dasharray="{dash}"')
        self.add("<line " + " ".join(a) + "/>")

    def circle(self, cx, cy, r, fill="none", stroke=None, sw=1, opacity=None):
        a = [f'cx="{cx:.2f}"', f'cy="{cy:.2f}"', f'r="{r:.2f}"']
        a.append(f'fill="{fill}"' if fill != "none" else 'fill="none"')
        if stroke:
            a.append(f'stroke="{stroke}"')
            a.append(f'stroke-width="{sw}"')
        if opacity is not None:
            a.append(f'opacity="{opacity}"')
        self.add("<circle " + " ".join(a) + "/>")

    def path(self, d, fill="none", stroke=None, sw=1, opacity=None, dash=None):
        a = [f'd="{d}"']
        a.append(f'fill="{fill}"' if fill != "none" else 'fill="none"')
        if stroke:
            a.append(f'stroke="{stroke}"')
            a.append(f'stroke-width="{sw}"')
        if opacity is not None:
            a.append(f'opacity="{opacity}"')
        if dash:
            a.append(f'stroke-dasharray="{dash}"')
        self.add("<path " + " ".join(a) + "/>")

    def svg(self, title, subtitle=""):
        head = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" font-family="{UI}">'
            f"<title>{esc(title)}</title>"
            f"<desc>{esc(subtitle)}</desc>"
            f'<rect width="{self.w}" height="{self.h}" fill="{PAPER}"/>'
        )
        return head + "\n".join(self.parts) + "</svg>\n"


# ── COMPONENT PRIMITIVES ─────────────────────────────────────────────────────

def card(c: Canvas, x, y, w, h, pad=20, rx=R_LG, fill=SURFACE, shadow=True):
    if shadow:
        c.rect(x, y + 1, w, h, fill="rgba(26,46,26,0.05)", rx=rx)
    c.rect(x, y, w, h, fill=fill, stroke=DIVIDER, rx=rx)
    return x + pad, y + pad


def pill(c: Canvas, x, y, label, kind="muted", size=10, h=18, pad=9):
    palette = {
        "forest": (FOREST_GLOW, FOREST),
        "ochre": (OCHRE_SOFT, OCHRE),
        "clay": (CLAY_SOFT, CLAY),
        "sage": (SAGE_SOFT, SAGE),
        "ok": (STATUS_OK_SOFT, STATUS_OK),
        "warn": (STATUS_WARN_SOFT, STATUS_WARN),
        "error": (CLAY_SOFT, CLAY),
        "unknown": (STATUS_UNKNOWN_SOFT, STATUS_UNKNOWN),
        "muted": ("rgba(90,90,74,0.08)", INK_SOFT),
        "invert": (PINE_DEEP, PAPER),
    }
    bg, fg = palette.get(kind, palette["muted"])
    w = _text_w(label, size, 0.02) + pad * 2
    c.rect(x, y, w, h, fill=bg, rx=h / 2)
    c.text(x + w / 2, y + h / 2 + size * 0.36, label.upper(), size=size, color=fg, weight=600,
           anchor="middle", spacing=0.02)
    return x + w


def _text_w(s, size, tracking=0.0):
    """Conservative width estimate for DM Sans / Libre Baskerville."""
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
    return u * size + tracking * size * max(0, len(str(s)) - 1)


def btn(c: Canvas, x, y, label, kind="secondary", size=11, h=28, pad=13):
    if kind == "primary":
        fill, fg, border = FOREST, "#ffffff", FOREST
    elif kind == "ghost":
        fill, fg, border = "none", INK_MID, "none"
    elif kind == "danger":
        fill, fg, border = CLAY_SOFT, CLAY, "rgba(160,64,32,0.25)"
    else:
        fill, fg, border = SURFACE, INK, DIVIDER_MID
    w = _text_w(label, size) + pad * 2
    c.rect(x, y, w, h, fill=fill, stroke=border, rx=R_SM)
    if fill != "none":
        pass
    c.text(x + w / 2, y + h / 2 + size * 0.36, label, size=size, color=fg, weight=500,
           anchor="middle")
    return x + w


def field(c: Canvas, x, y, w, label, value="", h=34, hint=None, mono=False, kind="select"):
    c.text(x, y - 5, label, size=10.5, color=PINE, weight=600)
    c.rect(x, y, w, h, fill=SURFACE, stroke=DIVIDER_MID, rx=R_SM)
    if kind == "textarea":
        lines = 0
        yy = y + 18
        for ln in value.split("\n"):
            c.text(x + 11, yy, ln, size=11.5, color=INK_MID if ln.startswith("…") else INK,
                   font=MONO if mono else UI)
            yy += 18
            lines += 1
        return y + h
    fam = MONO if mono else UI
    c.text(x + 11, y + h / 2 + 4, value, size=11.5, color=INK_MID, font=fam)
    if kind == "select":
        cx = x + w - 13
        c.path(f"M {cx-3.5} {y + h/2 - 2} L {cx} {y + h/2 + 2} L {cx+3.5} {y + h/2 - 2}",
               stroke=INK_MID, sw=1.6)
    if hint:
        c.text(x, y + h + 12, hint, size=10, color=INK_FAINT)
    return y + h


def tabs(c: Canvas, x, y, items, active, w_each=None, gap=2):
    """RoomTabs — the service-local nav row."""
    cx = x
    for it in items:
        w = w_each or (_text_w(it, 11.5) + 22)
        on = it == active
        if on:
            c.rect(cx, y, w, 30, fill=FOREST_GLOW, rx=R_SM)
        c.text(cx + w / 2, y + 20, it, size=11.5, color=FOREST if on else INK_MID,
               weight=600 if on else 500, anchor="middle")
        cx += w + gap
    return y + 30


def topnav(c: Canvas, x=0, y=0, w=1440, h=56, active="Design Studio", brand="Northstar OS"):
    c.rect(0, 0, w, h, fill=SURFACE, stroke=DIVIDER)
    # brand mark — the hollow 8-point star from the identity guide
    cx, cy, r = 26, h / 2, 11
    pts = []
    for i in range(16):
        ang = math.pi / 8 * i - math.pi / 2
        rr = r if i % 2 == 0 else r * 0.42
        pts.append(f"{cx + math.cos(ang) * rr:.2f},{cy + math.sin(ang) * rr:.2f}")
    c.path("M " + " L ".join(pts) + " Z", fill=FOREST, opacity=0.9)
    c.circle(cx, cy, r * 0.30, fill=PAPER)
    c.text(46, h / 2 + 5, brand, size=15, color=PINE_DEEP, font=SERIF, weight=700)
    links = ["Command Center", "SourceScout", "Golden Goose", "ListingForge", "AdPilot",
             "SocialPulse", active]
    lx = 220
    for l in links:
        tw = _text_w(l, 12)
        on = l == active
        if on:
            c.rect(lx - 10, h / 2 - 14, tw + 20, 28, fill=FOREST_GLOW, rx=R_SM)
        c.text(lx, h / 2 + 4, l, size=12, color=FOREST if on else INK_MID,
               weight=600 if on else 500)
        lx += tw + 26
    c.rect(w - 190, h / 2 - 13, 150, 26, fill=PAPER, stroke=DIVIDER, rx=R_SM)
    c.text(w - 178, h / 2 + 4, "Search rooms…", size=11, color=INK_FAINT)
    c.circle(w - 34, h / 2, 13, fill=FOREST)
    c.text(w - 34, h / 2 + 4, "TJ", size=9, color="#ffffff", weight=700, anchor="middle")
    return h


def page_header(c: Canvas, x, y, title, subtitle, actions=()):
    c.text(x, y + 16, title, size=26, color=PINE_DEEP, font=SERIF, weight=700)
    c.text(x, y + 38, subtitle, size=12, color=INK_MID)
    ax = x + 900
    for a in actions:
        ax = btn(c, ax, y + 6, a[0], kind=a[1] if len(a) > 1 else "secondary") + 8
    return y + 58


def data_notice(c: Canvas, x, y, w, tone, title, body, h=52):
    border, bg = {
        "sample": (DIVIDER_MID, SURFACE_RAISED),
        "internal": ("rgba(196,148,26,0.3)", OCHRE_SOFT),
        "warn": ("rgba(160,64,32,0.3)", CLAY_SOFT),
        "ok": ("rgba(45,106,45,0.3)", STATUS_OK_SOFT),
    }[tone]
    c.rect(x, y, w, h, fill=bg, stroke=border, rx=R)
    pill(c, x + 14, y + 9, tone, "unknown" if tone == "sample" else
         ("warn" if tone in ("internal", "warn") else "ok"), size=8.5, h=16, pad=7)
    c.text(x + 74, y + 21, title, size=11.5, color=PINE_DEEP, weight=600)
    c.text(x + 14, y + 40, body, size=10.5, color=INK_MID)
    return y + h


def rail_button(c: Canvas, x, y, w, icon, label, active=False, count=None):
    if active:
        c.rect(x, y, w, 52, fill=FOREST_GLOW, rx=R)
    _icon(c, x + w / 2, y + 19, icon, FOREST if active else INK_SOFT, 16)
    c.text(x + w / 2, y + 36, label, size=9, color=FOREST if active else INK_SOFT,
           anchor="middle", weight=600 if active else 400)
    if count is not None:
        c.rect(x + w - 15, y + 3, 13, 11, fill=OCHRE, rx=5.5)
        c.text(x + w - 8.5, y + 11, str(count), size=7.5, color="#ffffff", weight=700,
               anchor="middle")


_ICON_PATHS = {
    "target": "M8 1v4M8 11v4M1 8h4M11 8h4", "settings": "M3 8h10M8 3v10",
    "layers": "M8 1l6 3-6 3-6-3z M2 8l6 3 6-3 M2 11.5l6 3 6-3",
    "image": "M2 3h12v10H2z M4.5 6.5a1 1 0 100-2 1 1 0 000 2 M3 12l3.5-4 3 3 2-2 3.5 4",
    "type": "M3 4h10M8 4v9M6 13h4",
    "box": "M3 5l5-2 5 2v7l-5 2-5-2z M3 5l5 2 5-2 M8 7v7",
    "video": "M2 4h8v8H2z M10 7l4-2.5v7L10 9z",
    "sparkle": "M8 1l1.6 4.4L14 7l-4.4 1.6L8 13l-1.6-4.4L2 7l4.4-1.6z",
    "calendar": "M2 5h12v9H2z M2 8h12 M5 3v3 M11 3v3",
    "shield": "M8 1l5 2v5c0 3.5-3 6-5 7-2-1-5-3.5-5-7V3z",
    "chart": "M2 12V8M6 12V4M10 12V6M14 12V2",
    "palette": "M8 2a6 6 0 000 12c1.2 0 1.8-.8 1.8-1.8 0-1.4 1-2 2.2-2H14a3 3 0 003-3A6 6 0 008 2z",
    "search": "M7 1a6 6 0 100 12A6 6 0 007 1z M11 11l4 4",
    "check": "M2 8.5l4 4 8-9",
    "cube": "M2 5l6-3 6 3v6l-6 3-6-3z M8 2v12 M2 5l6 3 6-3",
    "tag": "M2 2h6l6 6-6 6-6-6z M5 5h.01",
    "bolt": "M9 1L3 9h4l-1 6 6-8H8z",
    "clock": "M8 1a7 7 0 100 14A7 7 0 008 1z M8 4v4l3 2",
    "list": "M3 4h10M3 8h10M3 12h7",
    "globe": "M8 1a7 7 0 100 14A7 7 0 008 1z M1 8h14 M8 1c-3 2-3 11 0 14 M8 1c3 2 3 11 0 14",
    "lock": "M3 7h10v7H3z M5 7V4a3 3 0 016 0v3",
    "wand": "M3 13L11 5 M12 2l.7 1.8L14.5 4.5l-1.8.7L12 7l-.7-1.8L9.5 4.5l1.8-.7z",
    "eye": "M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z M8 6a2 2 0 100 4 2 2 0 000-4",
}


def _icon(c: Canvas, cx, cy, name, color=INK_SOFT, size=16):
    d = _ICON_PATHS.get(name, _ICON_PATHS["target"])
    style = dict(stroke=color, sw=1.5)
    c.add(f'<g transform="translate({cx - size/2:.2f},{cy - size/2:.2f}) scale({size/16:.3f})">')
    c.path("M " + d, **style)
    c.add("</g>")


def thumb(c: Canvas, x, y, w, h, label, note="", kind="empty"):
    """The honest placeholder: dashed, hatched, never a fabricated render."""
    c.rect(x, y, w, h, fill="rgba(138,138,122,0.07)", stroke=DIVIDER_MID, rx=6, dash="6 4")
    c.rect(x, y, w, h, fill="url(#hatch)", rx=6)
    c.text(x + w / 2, y + h / 2 - 2, label, size=9.5, color=INK_SOFT, font=MONO,
           anchor="middle", spacing=0.06)
    if note:
        c.text(x + w / 2, y + h / 2 + 11, note, size=8.5, color=INK_FAINT, anchor="middle")


def hatched_dims(c: Canvas, x, y, w, h, label, dims, fg=PAPER):
    c.text(x + 14, y + 18, label, size=9.5, color="#a8b3a4", font=MONO, spacing=0.05)
    c.text(x + w - 14, y + 18, dims, size=9.5, color="#a8b3a4", font=MONO, anchor="end",
           spacing=0.05)


def stage(c: Canvas, x, y, w, h, label="Stage", dims="", children=None, badge=None):
    """Dark stage pane from studio.css .stage."""
    c.rect(x, y + 2, w, h, fill="rgba(26,46,26,0.16)", rx=R_LG)
    c.rect(x, y, w, h, fill="#1b2a1c", stroke="rgba(26,46,26,0.35)", rx=R_LG)
    c.rect(x, y, w, 30, fill="rgba(0,0,0,0.18)", rx=R_LG)
    c.rect(x, y + 22, w, 8, fill="rgba(0,0,0,0.18)")
    hatched_dims(c, x, y + 9, w - 200, h, label, dims)
    if badge:
        bx = x + w - 190
        pill(c, bx, y + 8, badge[0], badge[1] if len(badge) > 1 else "unknown", size=8.5, h=15, pad=7)
    c.rect(x, y + h - 32, w, 32, fill="rgba(0,0,0,0.18)", rx=R_LG)
    c.rect(x, y + h - 40, w, 8, fill="rgba(0,0,0,0.18)")
    if children:
        children()
    return x, y, w, h


def checkered(c: Canvas, x, y, w, h):
    """stage-checker backdrop."""
    c.rect(x, y, w, h, fill="#20291f")
    step = 18
    n = 0
    yy = y
    while yy < y + h:
        xx = x + (step if (n % 2) else 0)
        while xx < x + w:
            c.rect(xx, yy, step / 2, step / 2, fill="rgba(255,255,255,0.035)")
            xx += step
        yy += step / 2
        n += 1


def inspector(c: Canvas, x, y, w, h, title, sections=()):
    c.rect(x, y + 2, w, h, fill="rgba(26,46,26,0.05)", rx=R_LG)
    c.rect(x, y, w, h, fill=SURFACE, stroke=DIVIDER, rx=R_LG)
    c.rect(x, y, w, 40, fill=SURFACE, stroke=DIVIDER, rx=R_LG)
    c.line(x, y + 40, x + w, y + 40, stroke=DIVIDER)
    c.text(x + 14, y + 25, title, size=13, color=PINE_DEEP, font=SERIF, weight=600)
    return x + 14, y + 40, w - 28


def section(c: Canvas, x, y, w, title, right="", open_=True, body=None):
    c.path(f"M {x} {y+9} l 5 5 l 5 -5" if open_ else f"M {x} {y+4} l 5 5 l 0 -10",
           stroke=INK_SOFT, sw=1.2)
    c.text(x + 22, y + 13, title, size=11.5, color=PINE, weight=600)
    if right:
        c.text(x + w, y + 13, right, size=10, color=INK_SOFT, anchor="end")
    yy = y + 26
    if open_ and body:
        yy = body(yy)
    c.line(x, yy + 4, x + w, yy + 4, stroke=DIVIDER)
    return yy + 14


def format_grid(c: Canvas, x, y, w, groups, active_id, cols=4):
    """sp-formats — the format picker, grouped by family."""
    cy = y
    cell = (w - (cols - 1) * 8) / cols
    for g in groups:
        c.text(x, cy + 9, g["label"], size=9.5, color=INK_SOFT, weight=700, spacing=0.07)
        cy += 16
        for i, f in enumerate(g["formats"]):
            col, row = i % cols, i // cols
            fx = x + col * (cell + 8)
            fy = cy + row * 74
            on = f.get("id") == active_id
            c.rect(fx, fy, cell, 66, fill=FOREST_GLOW if on else SURFACE,
                   stroke=FOREST if on else DIVIDER, rx=R)
            bw = min(38, cell - 16)
            ar = f["w"] / f["h"]
            bw2, bh2 = (bw, bw / ar) if ar >= 1 else (bw * ar, bw)
            c.rect(fx + (cell - bw2) / 2, fy + 9, bw2, bh2, fill=SAGE_SOFT if on else BONE,
                   stroke=SAGE if on else DIVIDER_MID, rx=2)
            c.text(fx + cell / 2, fy + 34, f["label"], size=9.5,
                   color=PINE_DEEP if on else INK_MID, anchor="middle",
                   weight=600 if on else 400)
            c.text(fx + cell / 2, fy + 47, f"{f['w']}×{f['h']}", size=8.5, color=INK_FAINT,
                   font=MONO, anchor="middle")
        rows = math.ceil(len(g["formats"]) / cols)
        cy += rows * 74 + 10
    return cy


def meter(c: Canvas, x, y, w, pct, tone="forest"):
    c.rect(x, y, w, 6, fill=SURFACE_ACTIVE, rx=3)
    c.rect(x, y, w * max(0, min(1, pct)), 6, fill={"forest": FOREST, "ochre": OCHRE,
                                                  "clay": CLAY, "sage": SAGE}[tone], rx=3)
    return y + 6


def stat(c: Canvas, x, y, w, label, value, sub="", tone=None):
    c.rect(x, y, w, 62, fill=SURFACE_RAISED, stroke=DIVIDER, rx=R)
    c.text(x + 12, y + 17, label.upper(), size=8.5, color=INK_SOFT, spacing=0.05)
    col = {"forest": FOREST, "ochre": OCHRE, "clay": CLAY}.get(tone, PINE_DEEP)
    c.text(x + 12, y + 39, value, size=18, color=col, font=SERIF, weight=700)
    if sub:
        c.text(x + 12, y + 53, sub, size=9, color=INK_FAINT)


def kv_row(c: Canvas, x, y, w, k, v, mono=False, vsize=11):
    c.text(x, y, k, size=10.5, color=INK_SOFT)
    c.text(x + w, y, v, size=vsize, color=INK, font=MONO if mono else UI, anchor="end")
    c.line(x, y + 6, x + w, y + 6, stroke=DIVIDER)
    return y + 18


def swatch(c: Canvas, x, y, size, color, label=""):
    c.rect(x, y, size, size, fill=color, stroke=DIVIDER_MID, rx=3)
    if label:
        c.text(x + size / 2, y + size + 11, label, size=8, color=INK_FAINT, anchor="middle",
               font=MONO)


def spec_table(c: Canvas, x, y, w, rows, cols, colw):
    c.rect(x, y, w, 24, fill=SURFACE_RAISED, stroke=DIVIDER_MID, rx=0)
    cx = x
    for i, hd in enumerate(cols):
        c.text(cx + 10, y + 16, hd.upper(), size=8.5, color=INK_MID, weight=600, spacing=0.05)
        cx += colw[i]
    cy = y + 24
    for r in rows:
        c.rect(x, cy, w, 26, fill=SURFACE if rows.index(r) % 2 == 0 else SURFACE_RAISED,
               stroke=DIVIDER)
        cx = x
        for i, cellv in enumerate(r):
            c.text(cx + 10, cy + 17, cellv, size=10, color=INK, font=MONO if i == 0 else UI)
            cx += colw[i]
        cy += 26
    return cy


def arrow(c: Canvas, x1, y1, x2, y2, color=FOREST, sw=1.6, dash=None, head=5):
    ang = math.atan2(y2 - y1, x2 - x1)
    bx, by = x2 - head * math.cos(ang), y2 - head * math.sin(ang)
    c.line(x1, y1, bx, by, stroke=color, sw=sw, dash=dash)
    c.path(f"M {x2} {y2} L {bx - head*0.6*math.sin(ang):.2f} {by + head*0.6*math.cos(ang):.2f} "
           f"M {x2} {y2} L {bx + head*0.6*math.sin(ang):.2f} {by - head*0.6*math.cos(ang):.2f}",
           stroke=color, sw=sw)


def footer(c: Canvas, y, text, w=1440):
    c.line(28, y, w - 28, y, stroke=DIVIDER)
    c.text(28, y + 18, text, size=9.5, color=INK_FAINT)
