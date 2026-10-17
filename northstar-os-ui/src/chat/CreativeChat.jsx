// ═══════════════════════════════════════════════════════════════════════════
// CREATIVE CHAT — Simple-mode Master Brain shell (S1)
//
// The chat-first surface Creative Studio becomes when the global shell mode is
// Simple. Sessions are REAL backend records; turns stream over SSE with the
// separated thinking block, honest errors, cancel-as-partial, and an
// OpenCode-style message queue (type while it thinks; queued payloads send at
// the next safe pause point). Tools + the focus rail arrive in S2, voice in S3.
//
// Honesty contract:
//   • Nothing here fabricates a reply. Offline engine => the real fallback
//     text arrives over the stream and is marked.
//   • Stop sends a cancel and persists the partial as partial.
//   • The engine line under the session rail reports the real model name.
// ═══════════════════════════════════════════════════════════════════════════

import { useCallback, useEffect, useRef, useState } from 'react'
import Icon from '../components/Icon.jsx'
import { chatApi, streamTurn } from './api.js'

const SUGGESTIONS = [
  'Draft three directions for a Lion\u2019s Mane pouch \u2014 kraft, botanical, premium shelf.',
  'Write five Amazon main-image notes for a 6 oz mushroom powder pouch.',
  'Give me a shot list for a warm-linen product photo of a stand-up pouch.',
]

export default function CreativeChat() {
  const [railOpen, setRailOpen] = useState(true)
  const [sessions, setSessions] = useState([])
  const [activeId, setActiveId] = useState('')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [queue, setQueue] = useState([])
  const [streaming, setStreaming] = useState(false)
  const [turnId, setTurnId] = useState('')
  const [engine, setEngine] = useState(null)       // {ok, model} | {error}
  const [loadError, setLoadError] = useState('')
  const abortRef = useRef(null)
  const scrollRef = useRef(null)

  // One-time load: engine health + session list.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const h = await chatApi.health()
        if (!cancelled) setEngine(h)
      } catch (e) {
        if (!cancelled) setEngine({ error: e.message })
      }
      try {
        const r = await chatApi.sessions()
        if (!cancelled) setSessions(r.sessions || [])
      } catch (e) {
        if (!cancelled) setLoadError(e.message)
      }
    })()
    return () => {
      cancelled = true
      if (abortRef.current) abortRef.current.abort()
    }
  }, [])

  // Keep the stream pinned to the bottom while tokens arrive.
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [messages, streaming])

  const loadSession = useCallback(async (sid) => {
    setActiveId(sid)
    setMessages([])
    setQueue([])
    try {
      const r = await chatApi.messages(sid)
      setMessages((r.messages || []).map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content || '',
        thinking: m.thinking || '',
        status: (m.usage_json && m.usage_json.status) || 'done',
      })))
    } catch (e) {
      setLoadError(e.message)
    }
  }, [])

  const newChat = useCallback(() => {
    setActiveId('')
    setMessages([])
    setQueue([])
    setInput('')
    setLoadError('')
  }, [])

  const ensureSession = useCallback(async () => {
    if (activeId) return activeId
    const s = await chatApi.createSession({ mode: 'simple' })
    setSessions((prev) => [s, ...prev])
    setActiveId(s.id)
    return s.id
  }, [activeId])

  const runTurn = useCallback(async (content) => {
    const startedAt = Date.now()
    const botId = `local-a-${startedAt}`
    setMessages((prev) => [
      ...prev,
      { id: `local-u-${startedAt}`, role: 'user', content, thinking: '', status: 'done' },
      { id: botId, role: 'assistant', content: '', thinking: '', status: 'streaming', startedAt },
    ])
    setStreaming(true)
    const controller = new AbortController()
    abortRef.current = controller
    const patchBot = (fn) => setMessages((prev) => prev.map((m) => (m.id === botId ? fn(m) : m)))

    try {
      const sid = await ensureSession()
      await streamTurn(sid, { content, think: true }, ({ event, data }) => {
        if (event === 'start') {
          setTurnId(data.turn_id || '')
        } else if (event === 'thinking') {
          patchBot((m) => ({ ...m, thinking: m.thinking + (data.delta || '') }))
        } else if (event === 'token') {
          patchBot((m) => ({ ...m, content: m.content + (data.delta || '') }))
        } else if (event === 'notice') {
          patchBot((m) => ({ ...m, notices: [...(m.notices || []), data.code || 'notice'] }))
        } else if (event === 'error') {
          patchBot((m) => ({ ...m, status: 'error', error: data.reason || 'error', endedAt: Date.now() }))
        } else if (event === 'done') {
          patchBot((m) => ({
            ...m,
            serverId: data.message_id || m.serverId,
            status: data.status || 'done',
            endedAt: Date.now(),
          }))
        }
        // tool-start / tool-progress / tool-end / asset: wire-ready (S2)
      }, controller.signal)
    } catch (e) {
      if (e && e.name !== 'AbortError') {
        patchBot((m) => ({ ...m, status: 'error', error: e.message, endedAt: Date.now() }))
      } else {
        patchBot((m) => ({ ...m, status: 'cancelled', endedAt: Date.now() }))
      }
    } finally {
      setStreaming(false)
      setTurnId('')
      abortRef.current = null
      // Refresh the rail so an auto-titled session shows its real title.
      chatApi.sessions().then((r) => setSessions(r.sessions || [])).catch(() => {})
    }
  }, [ensureSession])

  const send = useCallback(() => {
    const content = input.trim()
    if (!content) return
    setInput('')
    if (streaming) {
      setQueue((q) => [...q, content])
      return
    }
    runTurn(content)
  }, [input, streaming, runTurn])

  // Drain the queue at the next safe pause point (turn finished).
  useEffect(() => {
    if (!streaming && queue.length) {
      const [next, ...rest] = queue
      setQueue(rest)
      runTurn(next)
    }
  }, [streaming, queue, runTurn])

  const stop = useCallback(() => {
    if (turnId) chatApi.cancelTurn(turnId).catch(() => {})
    if (abortRef.current) abortRef.current.abort()
  }, [turnId])

  const engineLine = engine && engine.ok
    ? `Engine: ${engine.model}`
    : engine && engine.error
      ? `Engine check failed: ${engine.error}`
      : 'Checking engine\u2026'

  return (
    <div className={`chat-shell ${railOpen ? '' : 'rail-hidden'}`}>
      <aside className="chat-rail" aria-label="Chat sessions" data-testid="chat-rail">
        <div className="chat-rail-head">
          <button type="button" className="btn btn-sm" onClick={newChat} data-testid="chat-new">
            <Icon name="plus" size={13} /> New chat
          </button>
          <button type="button" className="btn btn-sm btn-ghost" aria-label="Hide sessions"
            onClick={() => setRailOpen(false)}>&lsaquo;</button>
        </div>
        <div className="chat-rail-list">
          {sessions.length === 0 && (
            <div className="chat-rail-empty">No sessions yet — say something to start.</div>
          )}
          {sessions.map((s) => (
            <button key={s.id} type="button"
              className={`chat-rail-item ${s.id === activeId ? 'active' : ''}`}
              onClick={() => loadSession(s.id)}>
              {s.title || 'New chat'}
              <span className="chat-rail-meta">
                {s.updated_at ? String(s.updated_at).slice(0, 16).replace('T', ' ') : ''}
              </span>
            </button>
          ))}
        </div>
        <div className="chat-hint">{engineLine}</div>
      </aside>

      <section className="chat-col">
        <div className="chat-head">
          {!railOpen && (
            <button type="button" className="btn btn-sm btn-ghost" aria-label="Show sessions"
              onClick={() => setRailOpen(true)}>&rsaquo;</button>
          )}
          <h2>Creative Studio</h2>
          <span className="chat-head-sub">
            Master Brain chat &middot; <span className="chat-head-spark">Simple mode</span>
          </span>
          <span style={{ flex: 1 }} />
          {streaming && (
            <button type="button" className="btn btn-sm" onClick={stop} data-testid="chat-stop">
              Stop
            </button>
          )}
        </div>
        {loadError && <div className="chat-hint">Couldn&rsquo;t load sessions: {loadError}</div>}

        <div className="chat-stream" ref={scrollRef} data-testid="chat-stream">
          {messages.length === 0 && (
            <div className="chat-empty">
              <div className="chat-empty-rule" />
              <h3>What are we making?</h3>
              <p>
                Ask the Master Brain to draft packaging directions, listing copy, shot
                lists, or ad concepts. Everything streams here with its thinking shown;
                live image and dieline tools join this chat in S2.
              </p>
              <div className="chat-suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} type="button" className="chat-suggestion"
                    onClick={() => setInput(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m) => {
            const seconds = m.startedAt && m.endedAt
              ? Math.max(1, Math.round((m.endedAt - m.startedAt) / 1000))
              : null
            return (
              <div key={m.id}
                className={`chat-msg ${m.role} ${m.status === 'error' ? 'error' : ''}`}>
                {m.role === 'assistant' && m.thinking && (
                  <details className="chat-thinking" open={m.status === 'streaming'}>
                    <summary>
                      <span className="chat-spark" />
                      {m.status === 'streaming'
                        ? 'Thinking\u2026'
                        : `Thought${seconds ? ` for ${seconds}s` : ''} \u00b7 ${m.thinking.length} chars`}
                    </summary>
                    <div className="chat-thinking-body">{m.thinking}</div>
                  </details>
                )}
                {m.content && <div className="chat-bubble">{m.content}</div>}
                {!m.content && m.status === 'streaming' && (
                  <div className="chat-bubble"><span className="chat-caret" /></div>
                )}
                {m.status === 'error' && (
                  <div className="chat-hint">
                    Error: {m.error || 'unknown'} — nothing was fabricated; retry when
                    the engine is up.
                  </div>
                )}
                {m.status === 'cancelled' && (
                  <div className="chat-hint">Stopped — the partial answer was saved as partial.</div>
                )}
              </div>
            )
          })}
        </div>

        <div className="chat-composer">
          {queue.length > 0 && (
            <div className="chat-queue-note">
              <span className="spark">{queue.length} queued</span> — sends when the
              current turn finishes &middot; next: &ldquo;{queue[0].slice(0, 60)}&rdquo;
            </div>
          )}
          <div className="chat-composer-box">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  send()
                }
              }}
              placeholder={streaming
                ? 'Type \u2014 it queues and sends next\u2026'
                : 'Describe what you want to make\u2026'}
              rows={1}
              aria-label="Chat message"
              data-testid="chat-input"
            />
            <button type="button" className="btn btn-primary btn-sm" onClick={send}
              disabled={!input.trim()} data-testid="chat-send" aria-label="Send">
              Send
            </button>
          </div>
          <div className="chat-hint">
            Enter sends &middot; Shift+Enter newline &middot; Stop saves the partial as
            partial &middot; Focus rail lands in S2, voice in S3.
          </div>
        </div>
      </section>
    </div>
  )
}
