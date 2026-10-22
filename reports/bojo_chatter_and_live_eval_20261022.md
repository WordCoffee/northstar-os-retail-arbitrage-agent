# Bojo chatter contract + live answer grading — 2026-10-22

Two follow-ups to the Continuous Improvement Engine, both measured.

## 1. The answer starts with the answer

The model is told not to preamble; instruction-following is not a guarantee, so
the stream itself is filtered.

| behaviour | implementation |
|---|---|
| leading "Sure!", "Certainly.", "Let me…", "Here's…" | dropped from the SSE stream before it reaches the operator |
| opener split across deltas ("Cert" + "ainly.") | buffered until it resolves, then dropped |
| clean answer | emitted on the first delta — **no added latency** |
| trailing "let me know if…" / "hope this helps" | stripped **before persistence**, completed turns only |
| partial / cancelled turn | stored **verbatim** — a cut-off answer is evidence, not something to tidy |

Files: `chat_adapter.strip_preamble_events`, `strip_preamble_text`,
`strip_closing_filler`; wired through `stream_turn` and `chat_router._persist`.

Guardrail: if an opener never ends, the buffered text is released rather than
swallowed, so the filter can never delete a real answer.

## 2. The operator's judgement now feeds the loop

Every Bojo answer carries **Right** / **Wrong** in its receipt row. A click posts
to `/api/v1/improvement/feedback`:

- `up` → a quality confirmation;
- `down` → a gap the nightly cycle can research (the answer text is attached as
  evidence, capped at 600 chars);
- best-effort by design: a failed rating never disturbs the conversation.

## 3. Live answer grading (opt-in)

`python -m cie_loop --cycle --live --live-limit N` asks the model the golden
questions with the current packs in context and grades the answers with the same
deterministic graders used everywhere else (limits, banned claims, required
fields, citations, one-question rule).

- It is a **quality trend, not the promotion gate** — promotion stays
  coverage-based, so a bad model day cannot rewrite selling rules.
- Results are stored in the `evals` table and printed in the cycle report.
- First real sample: **0.8 on 1 question**, with the failing check named.

## 4. The three modes are now in the composer

`Mode: Creative · Standard · Thinking` sits next to Thinking/Style and travels
with every turn. The contract is server-owned (`chat_router._MODE_CONTRACT`), so
the client can only choose a posture, never widen what the model may do:

| mode | shape | effort |
|---|---|---|
| Creative | 3 options, one line of rationale each, drafts without asking | medium |
| Standard | answer in the first sentence, max one clarifying question | medium + discipline |
| Thinking | assumptions, verify the checkable parts, name uncertainty | xhigh |

Explicit "off" still wins over any mode.

## Gates

- **128 passed / 0 failed** (`test_cie`, `test_chatter`, chat core, tools, turn
  contract, plan, shell modes).
- UI build: **0 errors**.
- Live path verified against the real local model, not only fixtures.

## Still open

- Golden set is 20 questions; the target is 100 with a rotating hold-out.
- Feedback needs a "what was wrong" free-text field (the API already accepts
  `note`; the UI sends the answer text for now).
- `--live` runs are serial and slow (~30–60 s per answer). A nightly run should
  cap at 5 questions until the box has headroom.
