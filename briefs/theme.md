# Brief — Celestial theme (§11B.2)

**Written in the operator's words:** *"A modern, polished, distinctive galactic interface inspired by
interstellar space: visible galaxies, planets, shooting stars, depth, and restrained background motion
around a readable chatbot."* The Interstellar theme was requested; a plain black background shipped.
**Status: unmet.** This brief must be approved before I touch the theme.

## Intended experience

Opening NorthstarOS should feel like looking into deep space from inside a lit cockpit: the room is
dark and calm, the work surfaces are frosted glass, and the galaxy is *visible but never competing*
with the text. Motion is slow enough that you notice it only after a few seconds, and it stops
entirely for anyone who asks the OS to reduce motion.

## Pass/fail checks (6)

| # | Check | How it is evidenced |
|---|---|---|
| T1 | Background is a **layered scene**, not flat: gradient + 3 star depths + nebula wash + one warm accretion glow behind the chat column | desktop screenshot; layer list from the component |
| T2 | The **accretion glow** sits behind the chat box and is warm amber/gold, not purple | desktop screenshot, pixel sample at the glow centre |
| T3 | Palette is space black / midnight blue with amber-gold accents and silver-blue secondary text; **no purple-dominant palette** | palette swatches + screenshot |
| T4 | Body text on the panel meets **≥ 4.5:1** contrast at the **brightest animation frame** | computed contrast ratio, recorded |
| T5 | **Parallax is slow and purposeful** — measurable drift over 3 s, no visible judder; **reduced-motion freezes it** | two timed screenshots + reduced-motion screenshot |
| T6 | **Desktop and mobile** both pass, and the canvas does not slow chat (no dropped-frame spikes on send) | two screenshots at recorded viewports + timing note |

## Explicit non-goals

- No bright galaxy behind the reading surface.
- No continuous high-cost animation; must not compete with ComfyUI/Ollama for the GPU.
- No third-party tracking or image assets.

## Out of scope for this brief

Simple Mode layout, Package Designer output — separate briefs.
