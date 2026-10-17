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
import { chatApi, chatVoice, streamTurn, assetFileUrl } from './api.js'

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
  const [recording, setRecording] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [voiceNote, setVoiceNote] = useState('')
  const abortRef = useRef(null)
  const scrollRef = useRef(null)
  const mediaRef = useRef(null)
  const chunksRef = useRef([])

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
      setMessages((r.messages || []).map((m) => {
        const parts = Array.isArray(m.parts_json) ? m.parts_json : []
        return {
          id: m.id,
          role: m.role,
          content: m.content || '',
          thinking: m.thinking || '',
          status: (m.usage_json && m.usage_json.status) || 'done',
          tools: parts.filter((p) => p.type === 'tool').map((p, i) => ({
            call_id: p.call_id || `t-${i}`,
            name: p.name,
            status: p.ok ? 'done' : 'error',
            ok: !!p.ok,
            summary: p.summary,
            error: p.error,
          })),
          assets: parts.filter((p) => p.type === 'tool')
            .flatMap((p) => (p.assets || []).map((id) => ({ id, name: 'asset' }))),
        }
      }))
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
        } else if (event === 'tool-start') {
          patchBot((m) => ({
            ...m,
            tools: [...(m.tools || []), {
              call_id: data.call_id, name: data.name, args: data.args,
              status: 'running', pct: null, label: 'queued', ok: null,
            }],
          }))
        } else if (event === 'tool-progress') {
          patchBot((m) => ({
            ...m,
            tools: (m.tools || []).map((tj) => (tj.call_id === data.call_id
              ? { ...tj, pct: data.pct, label: data.label || tj.label }
              : tj)),
          }))
        } else if (event === 'tool-end') {
          patchBot((m) => ({
            ...m,
            tools: (m.tools || []).map((tj) => (tj.call_id === data.call_id
              ? { ...tj, status: data.ok ? 'done' : 'error', ok: !!data.ok,
                  summary: data.summary, error: data.error }
              : tj)),
          }))
        } else if (event === 'asset') {
          patchBot((m) => ({
            ...m,
            assets: [...(m.assets || []).filter((a) => a.id !== data.id), data],
          }))
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

  const startRecording = useCallback(async () => {
    setVoiceNote('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const rec = new MediaRecorder(stream)
      chunksRef.current = []
      rec.ondataavailable = (e) => { if (e.data && e.data.size) chunksRef.current.push(e.data) }
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        setRecording(false)
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || 'audio/webm' })
        if (!blob.size) { setVoiceNote('Heard nothing — no audio captured.'); return }
        setTranscribing(true)
        try {
          const r = await chatVoice.transcribe(blob)
          const text = String((r && r.text) || '').trim()
          if (text) setInput((prev) => (prev ? `${prev} ${text}` : text))
          else setVoiceNote('Heard nothing — nothing was transcribed (local whisper).')
        } catch (e) {
          setVoiceNote(`Voice unavailable: ${e.message}`)
        } finally {
          setTranscribing(false)
        }
      }
      mediaRef.current = rec
      rec.start()
      setRecording(true)
    } catch (e) {
      setVoiceNote(`Microphone unavailable: ${e.message}`)
    }
  }, [])

  const stopRecording = useCallback(() => {
    const rec = mediaRef.current
    if (rec && rec.state !== 'inactive') rec.stop()
  }, [])

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
                {m.role === 'assistant' && (m.tools || []).length > 0 && (
                  <div className="chat-tools" data-testid="chat-tools">
                    {m.tools.map((tj) => (
                      <div key={tj.call_id} className={`chat-tool ${tj.status}`}>
                        <span className="chat-tool-name">{tj.name}</span>
                        <span className="chat-tool-state">
                          {tj.status === 'running'
                            ? (tj.pct != null ? `${tj.pct}%` : (tj.label || 'working\u2026'))
                            : tj.status === 'done' ? '\u2713 done' : '\u2717 failed'}
                        </span>
                        {tj.status === 'running' && (
                          <span className="chat-tool-bar">
                            <i className={tj.pct != null ? '' : 'indet'}
                              style={tj.pct != null ? { width: `${tj.pct}%` } : undefined} />
                          </span>
                        )}
                        {tj.status === 'error' && tj.error && (
                          <span className="chat-tool-error">{tj.error}</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                {m.role === 'assistant' && (m.assets || []).length > 0 && (
                  <div className="chat-assets" data-testid="chat-assets">
                    {m.assets.map((a, i) => (a.id ? (
                      <a key={`${a.id}-${i}`} className="chat-asset-card"
                        href={assetFileUrl(a.id)} target="_blank" rel="noreferrer">
                        {(!a.kind || a.kind === 'image') && (
                          <img src={assetFileUrl(a.id)} alt={a.name || 'generated asset'} loading="lazy" />
                        )}
                        <span className="chat-asset-meta">
                          {a.name || 'asset'}
                          {a.width && a.height ? ` \u00b7 ${a.width}\u00d7${a.height}` : ''}
                        </span>
                      </a>
                    ) : null))}
                  </div>
                )}
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
            {recording ? (
              <button type="button" className="btn btn-sm btn-danger" onClick={stopRecording}
                data-testid="chat-voice-stop" aria-label="Stop recording">
                &#9632; Stop recording
              </button>
            ) : (
              <button type="button" className="btn btn-sm" onClick={startRecording}
                disabled={transcribing} data-testid="chat-voice"
                aria-label="Record voice message" title="Push-to-talk (local whisper.cpp)">
                {transcribing ? 'Transcribing\u2026' : '\u25CF Voice'}
              </button>
            )}
            <button type="button" className="btn btn-primary btn-sm" onClick={send}
              disabled={!input.trim()} data-testid="chat-send" aria-label="Send">
              Send
            </button>
          </div>
          <div className="chat-hint">
            {voiceNote && <span className="chat-voice-note">{voiceNote} &middot; </span>}
            Enter sends &middot; Shift+Enter newline &middot; Stop saves the partial as
            partial &middot; Voice records locally and transcribes with whisper.cpp
            (no audio leaves this machine).
          </div>
        </div>
      </section>
    </div>
  )
}
