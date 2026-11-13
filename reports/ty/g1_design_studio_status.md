# G1 — Design Studio: measured status, 2026-11-13

The launch gate asks for one click path that **generates a picture, persists it, and reads it back**.
Both halves were probed; neither is satisfied yet, and neither failure is a code mystery.

## 1. Generation: blocked on the render lane, measured

```
GET /api/design-studio/lanes/status
  engine.comfyui.reachable = false
  engine.comfyui.armed     = true
  note: "Armed but unreachable at http://127.0.0.1:8188 - start ComfyUI."
```

```
python -c "import ram_governor; ram_governor.status()"
  free_gb 3.03   max_builders 4   paused false
```

The seller render lane refuses below **3.0 GB free RAM** (`tools/seller_tester/scene_render.py:254`),
so the box has **0.03 GB of margin** — starting ComfyUI (which holds ~13 GB VRAM and its own RSS)
would cross the floor and thrash a box the owner is working on. The render was therefore not
started, and this is recorded as a refusal rather than attempted and blamed on the lane.

**Unblock, in order:** free ~1.5 GB RAM (close unused Chrome tabs / the second uvicorn) →
`tools/start_comfyui.ps1` → request a 1024² image from the studio → the G1 spec below runs for real.

## 2. Persistence: the canvas autosaves locally, not on the server

The studio's own asset rail says it plainly, in the UI:

> "ASSETS IN THIS DESIGN — Nothing uploaded yet. **The canvas autosaves each image it holds.**"

So a reload keeps a design **on that browser** and loses it on another device or after clearing
storage. There is no server-side project record to read back, which is what "persist" means in the
launch gate. `GET /api/design-studio/assets` does return server assets (dielines, renders, composed
mockups) — those persist — but a *canvas design* is not one of them.

**This is the gap, stated plainly:** the studio can make a deliverable, and it can keep it locally;
it cannot yet hand the seller the same design back from the server.

## 3. What is therefore queued

| job | blocked on |
|---|---|
| `g1-design-studio` (generation half) | free RAM + ComfyUI start |
| `g1-design-studio-persist` (new, small) | a server-side project store for canvas designs: `POST/GET /api/design-studio/projects`, autosave on change, load on open |

The second is a real feature, and the order allows only the listed work — it is part of this gate,
so it is queued rather than invented elsewhere.

## 4. What was not claimed

- No render was attempted, so no picture was produced in this pass.
- No persistence test passes, so G1 for Design Studio stays **unproven**. The scorecard's 89.5 is
  unchanged and is not evidence for this gate.
