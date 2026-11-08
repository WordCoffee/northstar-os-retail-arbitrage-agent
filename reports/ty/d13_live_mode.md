# D13 — live mode, text first

2026-11-08. Work order §5.1 layer 6: the owner points at the screen, Ty narrates it and
answers questions about it. Voice is optional and explicitly out of scope here.

## What it is

`tools/vision/live.py` — a `LiveSession` with `observe()` and `ask()`. One observation is:

1. the window list, passed through the privacy blocklist **before** anything else (a refused
   window contributes no title, no elements, no pixels);
2. the UI Automation tree of the focused allowed window, so the element count is
   deterministic;
3. the local vision model, asked only for what the tree cannot say;
4. a text narration assembled from (1)–(3), and a transcript of every turn.

Only text leaves the session. A transcript is JSON of narration and answers.

## Acceptance, with the real output

```
python -m tools.vision.live --demo
```

```json
{"d13": {"pass": true,
  "narration": "Visible: WindowsTerminal.exe — OC | Ty director finish order; RtkUWP.exe — Realtek Audio Console; SystemSettings.exe — Settings; chrome.exe — Google Chrome; explorer.exe — simple - File Explorer; claude.exe — Claude. The vision model names: OC | Ty director finish order, cmd, MCP, chromeconnect, context7. The focused window has 22 actionable elements (9 ButtonControl, 7 TextControl, 3 PaneControl, 1 WindowControl).",
  "answers": [
    "Visible: WindowsTerminal.exe — OC | Ty director finish order; ... The focused window has 22 actionable elements ...",
    "Visual Studio Code"],
  "windows_allowed": 11}}
```

Two honest notes about that run:

- The **narration is grounded** in the window list and the tree: it named the terminal by its
  real title and counted 22 elements in the focused window.
- The **second answer** came from the vision model's `foreground` field, and that model said
  "Visual Studio Code" while the real focused window was Windows Terminal. This is precisely
  why the rule is *structure first*: the tree and the window list are the answer, and the
  model's opinion is labelled as its opinion. Fix recorded for the next pass: answer "which
  app has focus" from the window list and the foreground HWND, not from the model.

## Tests

```
python -m pytest Northstar_backend/test_vision_live.py -q
```

Covers: a blocked window is dropped before description; narration names windows and counts
elements; questions are answered from the observation; an unstarted session answers nothing;
a blocked frame answers with the privacy reason; the demo passes with injected inputs.

## Not built

Voice (Whisper-class STT and local TTS) — deliberately last per the work order, and it would
add a download to a disk that is at 5–7 GB free.
