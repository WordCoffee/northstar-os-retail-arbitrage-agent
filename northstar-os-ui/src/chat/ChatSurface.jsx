// ═══════════════════════════════════════════════════════════════════════════
// CHAT SURFACE (V3) — the universal Master Brain chat.
//
// One component backs every Simple-mode surface:
//   • NorthstarOS shell  → focus "auto" (or whatever the operator picked)
//   • Creative Studio    → focus "create"
//   • AutothinK surface  → focus "autothink"
//
// Sessions are REAL backend records scoped to the account; turns stream over
// SSE (thinking separated, tool events, honest errors, cancel-as-partial).
// The active focus is sent with session creation and PATCHed when it changes;
// the SERVER restricts which tools are offered to the model per focus.
//
// V3 additions over S1: markdown rendering, tool args/summaries/pct+phase,
// reading scroll respect + jump pill, edit & resend, retry, copy, queue chips
// with remove, auto-grow composer, per-focus resume, session rename+search,
// artifact lightbox with download, context receipts, voice status + meter.
//
// Honesty contract:
//   • Nothing here fabricates a reply — offline engine ⇒ the real fallback
//     text arrives over the stream and is marked.
//   • Stop persists the partial as partial.
//   • The engine line reports the real model name.
// ═══════════════════════════════════════════════════════════════════════════

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Icon from '../components/Icon.jsx'
import { chatApi, chatVoice, streamTurn, assetFileUrl } from './api.js'

const DEFAULT_SUGGESTIONS = [
  'What should I focus on today across my brands?',
  'Show status of the local engine and what is ready to run.',
]

const TOOL_LABELS = {
  system_status: 'Checking the local engine',
  list_templates: 'Listing dieline templates',
  design_brief: 'Structuring the brief',
  create_dieline: 'Building the dieline',
  generate_image: 'Rendering the image locally',
  seo_check: 'Checking the latest listing revision',
}

function toolLabel(name, fallback) {
  return TOOL_LABELS[name] || fallback || name
}

function sessionKey(focusId) {
  return `ns-chat-session:${focusId || 'auto'}`
}

function relTime(ts) {
  if (!ts) return ''
  try {
    const t = new Date(ts).getTime()
    const mins = Math.round((Date.now() - t) / 60000)
    if (mins < 1) return 'now'
    if (mins < 60) return `${mins}m ago`
    const hours = Math.round(mins / 60)
    if (hours < 24) return `${hours}h ago`
    return String(ts).slice(0, 10)
  } catch { return '' }
}

// ── Markdown-lite (safe subset: no raw HTML ever) ───────────────────────────

function Inline({ text, keyPrefix }) {
  const out = []
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\((https?:\/\/[^\s)]+)\)|https?:\/\/[^\s<>)]+)/g
  let last = 0
  let m
  let i = 0
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index))
    const tok = m[0]
    if (tok.startsWith('**')) {
      out.push(<strong key={`${keyPrefix}-b${i}`}>{tok.slice(2, -2)}</strong>)
    } else if (tok.startsWith('`')) {
      out.push(<code key={`${keyPrefix}-c${i}`}>{tok.slice(1, -1)}</code>)
    } else if (tok.startsWith('[')) {
      const mm = tok.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/)
      out.push(
        <a key={`${keyPrefix}-a${i}`} href={mm[2]} target="_blank" rel="noreferrer">{mm[1]}</a>,
      )
    } else {
      out.push(
        <a key={`${keyPrefix}-u${i}`} href={tok} target="_blank" rel="noreferrer">{tok}</a>,
      )
    }
    last = m.index + tok.length
    i += 1
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

function RichText({ text }) {
  const blocks = useMemo(() => {
    const src = String(text || '')
    const parts = []
    const fence = /```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g
    let last = 0
    let m
    let i = 0
    while ((m = fence.exec(src)) !== null) {
      if (m.index > last) parts.push({ kind: 'text', text: src.slice(last, m.index) })
      parts.push({ kind: 'code', lang: m[1], text: m[2] })
      last = m.index + m[0].length
      i += 1
    }
    if (last < src.length) parts.push({ kind: 'text', text: src.slice(last) })
    return parts
  }, [text])

  return (
    <>
      {blocks.map((b, bi) => (b.kind === 'code' ? (
        <pre key={`cb-${bi}`} className="chat-code">
          <code>{b.text.replace(/\n$/, '')}</code>
        </pre>
      ) : (
        String(b.text).split(/\n{2,}/).map((para, pi) => {
          const lines = para.split('\n')
          const isList = lines.every((ln) => /^\s*[-*]\s+/.test(ln) || !ln.trim())
          const head = lines.length === 1 && /^#{1,4}\s+/.test(lines[0])
          if (head) {
            return <h4 key={`p-${bi}-${pi}`}><Inline text={lines[0].replace(/^#{1,4}\s+/, '')} keyPrefix={`h-${bi}-${pi}`} /></h4>
          }
          if (isList) {
            return (
              <ul key={`p-${bi}-${pi}`}>
                {lines.filter((ln) => ln.trim()).map((ln, li) => (
                  <li key={`li-${li}`}><Inline text={ln.replace(/^\s*[-*]\s+/, '')} keyPrefix={`l-${bi}-${pi}-${li}`} /></li>
                ))}
              </ul>
            )
          }
          return (
            <p key={`p-${bi}-${pi}`}>
              {lines.map((ln, li) => (
                <span key={`ln-${li}`}>
                  <Inline text={ln} keyPrefix={`t-${bi}-${pi}-${li}`} />
                  {li < lines.length - 1 ? <br /> : null}
                </span>
              ))}
            </p>
          )
        })
      )))}
    </>
  )
}

// ── The chat surface ────────────────────────────────────────────────────────

export default function ChatSurface({
  focus,
  heading = 'Master Brain',
  sub = 'Simple view',
  onOpenAdvanced = null,
  onBusyChange = null,
}) {
  const focusId = focus?.id || 'auto'
  const suggestions = (focus?.suggestions && focus.suggestions.length)
    ? focus.suggestions : DEFAULT_SUGGESTIONS

  const [railOpen, setRailOpen] = useState(() => (
    typeof window === 'undefined' ? true : window.innerWidth > 900
  ))
  const [sessions, setSessions] = useState([])
  const [sessionFilter, setSessionFilter] = useState('')
  const [renamingId, setRenamingId] = useState('')
  const [renameDraft, setRenameDraft] = useState('')
  const [activeId, setActiveId] = useState('')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [queue, setQueue] = useState([])
  const [streaming, setStreaming] = useState(false)
  const [turnId, setTurnId] = useState('')
  const [engine, setEngine] = useState(null)       // {ok, model, tools} | {error}
  const [loadError, setLoadError] = useState('')
  const [voiceStatus, setVoiceStatus] = useState(null)  // {ok, detail} | null
  const [recording, setRecording] = useState(false)
  const [recordSeconds, setRecordSeconds] = useState(0)
  const [transcribing, setTranscribing] = useState(false)
  const [voiceNote, setVoiceNote] = useState('')
  const [pinned, setPinned] = useState(true)
  const [lightbox, setLightbox] = useState(null)   // {id, name, kind}
  const [editing, setEditing] = useState(null)     // {id, text}
  const [paused, setPaused] = useState(false)     // human-in-the-loop handover
  const abortRef = useRef(null)
  const scrollRef = useRef(null)
  const mediaRef = useRef(null)
  const chunksRef = useRef([])
  const recordTimer = useRef(null)
  const inputRef = useRef(null)
  const focusRef = useRef(focus)
  focusRef.current = focus

  // One-time load: engine health + voice status + session list.
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
        const v = await chatVoice.status()
        if (!cancelled) setVoiceStatus(v)
      } catch { /* voice chip stays UNKNOWN */ }
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
      if (recordTimer.current) clearInterval(recordTimer.current)
    }
  }, [])

  const loadSession = useCallback(async (sid, { remember = true } = {}) => {
    setActiveId(sid)
    setMessages([])
    setQueue([])
    setEditing(null)
    if (remember) {
      try { localStorage.setItem(sessionKey(focusId), sid) } catch { /* storage */ }
    }
    try {
      const r = await chatApi.messages(sid)
      if (r.session && r.session.focus_json && r.session.focus_json.mode
          && r.session.focus_json.mode !== focusRef.current?.id) {
        // Session belongs to another focus — keep the operator's current focus
        // but say so instead of silently retargeting.
        setLoadError(`This session was started in the "${r.session.focus_json.mode}" focus.`)
      }
      setMessages((r.messages || []).map((m) => {
        const parts = Array.isArray(m.parts_json) ? m.parts_json : []
        return {
          id: m.id,
          role: m.role,
          content: m.content || '',
          thinking: m.thinking || '',
          status: (m.usage_json && m.usage_json.status) || 'done',
          model: m.model || '',
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
          cards: parts.filter((p) => p.type === 'card').map((p, i) => ({
            id: `card-${i}`,
            title: p.title || 'Card',
            rows: Array.isArray(p.rows) ? p.rows : [],
            action: p.action || null,
            ok: !!p.ok,
          })),
        }
      }))
    } catch (e) {
      setLoadError(e.message)
    }
  }, [focusId])

  // Resume the last session this focus was using, else the most recent one.
  useEffect(() => {
    let sid = ''
    try { sid = localStorage.getItem(sessionKey(focusId)) || '' } catch { /* storage */ }
    if (!sid && sessions.length) sid = sessions[0].id
    if (sid) loadSession(sid, { remember: false })
  }, [focusId, sessions, loadSession])

  // Auto-pin the stream only while the reader is at the bottom.
  useEffect(() => {
    const el = scrollRef.current
    if (!el || !pinned) return
    el.scrollTop = el.scrollHeight
  }, [messages, streaming, pinned])

  const onStreamScroll = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 48
    setPinned(atBottom)
  }, [])

  const newChat = useCallback(() => {
    setActiveId('')
    setMessages([])
    setQueue([])
    setInput('')
    setLoadError('')
    setEditing(null)
    try { localStorage.removeItem(sessionKey(focusId)) } catch { /* storage */ }
    inputRef.current?.focus()
  }, [focusId])

  // Fork (rewind): branch a NEW session from any persisted message. The parent
  // is never touched — a non-destructive rewind, not a destructive edit.
  const forkFrom = useCallback(async (messageId) => {
    if (!activeId || !messageId || String(messageId).startsWith('local-')) return
    try {
      const out = await chatApi.forkSession(activeId, { upto_message_id: messageId })
      if (out && out.session) {
        setSessions((prev) => [out.session, ...prev])
        loadSession(out.session.id)
      }
    } catch (e) {
      setLoadError(e.message)
    }
  }, [activeId, loadSession])

  const ensureSession = useCallback(async () => {
    if (activeId) return activeId
    const f = focusRef.current
    const s = await chatApi.createSession({
      mode: 'simple',
      focus: { mode: f?.id || 'auto', label: f?.label || 'Auto' },
    })
    setSessions((prev) => [s, ...prev])
    setActiveId(s.id)
    try { localStorage.setItem(sessionKey(focusId), s.id) } catch { /* storage */ }
    return s.id
  }, [activeId, focusId])

  // Switching focus mid-session re-points the brain (server persists it).
  useEffect(() => {
    if (!activeId) return
    const t = setTimeout(() => {
      chatApi.patchSession(activeId, {
        focus: { mode: focusId, label: focusRef.current?.label || focusId },
      }).catch(() => { /* focus patch is best-effort; turn still carries history */ })
    }, 250)
    return () => clearTimeout(t)
  }, [activeId, focusId])

  const runTurn = useCallback(async (content) => {
    const startedAt = Date.now()
    const botId = `local-a-${startedAt}`
    setMessages((prev) => [
      ...prev,
      { id: `local-u-${startedAt}`, role: 'user', content, thinking: '', status: 'done' },
      { id: botId, role: 'assistant', content: '', thinking: '', status: 'streaming',
        startedAt, prompt: content },
    ])
    setStreaming(true)
    setPinned(true)
    const controller = new AbortController()
    abortRef.current = controller
    const patchBot = (fn) => setMessages((prev) => prev.map((m) => (m.id === botId ? fn(m) : m)))

    try {
      const sid = await ensureSession()
      await streamTurn(sid, { content, think: true }, ({ event, data }) => {
        if (event === 'start') {
          setTurnId(data.turn_id || '')
          patchBot((m) => ({ ...m, model: data.model || m.model }))
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
              ? { ...tj, pct: data.pct != null ? data.pct : tj.pct, label: data.label || tj.label }
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
          patchBot((m) => ({ ...m, notices: [...(m.notices || []), data.detail || data.code || 'notice'] }))
        } else if (event === 'error') {
          patchBot((m) => ({ ...m, status: 'error', error: data.reason || 'error', endedAt: Date.now() }))
        } else if (event === 'done') {
          patchBot((m) => ({
            ...m,
            serverId: data.message_id || m.serverId,
            status: data.status || 'done',
            usage: data.usage || m.usage,
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
      chatApi.sessions().then((r) => setSessions(r.sessions || [])).catch(() => {})
    }
  }, [ensureSession])

  const send = useCallback((raw) => {
    const content = (raw != null ? raw : input).trim()
    if (!content) return
    setInput('')
    setEditing(null)
    if (paused) setPaused(false)   // a human message hands control back to the agent
    if (streaming) {
      setQueue((q) => [...q, content])
      return
    }
    runTurn(content)
  }, [input, streaming, runTurn, paused])

  // Drain the queue at the next safe pause point (turn finished). While the
  // human has taken over (paused), nothing drains — the agent waits.
  useEffect(() => {
    if (!streaming && queue.length && !paused) {
      const [next, ...rest] = queue
      setQueue(rest)
      runTurn(next)
    }
  }, [streaming, queue, runTurn, paused])

  const stop = useCallback(() => {
    if (turnId) chatApi.cancelTurn(turnId).catch(() => {})
    if (abortRef.current) abortRef.current.abort()
  }, [turnId])

  // ── Voice (local whisper.cpp; no audio leaves the machine) ────────────────

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
        if (recordTimer.current) { clearInterval(recordTimer.current); recordTimer.current = null }
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
      setRecordSeconds(0)
      recordTimer.current = setInterval(() => setRecordSeconds((s) => s + 1), 1000)
    } catch (e) {
      setVoiceNote(`Microphone unavailable: ${e.message}`)
    }
  }, [])

  const stopRecording = useCallback(() => {
    const rec = mediaRef.current
    if (rec && rec.state !== 'inactive') rec.stop()
  }, [])

  const voiceDisabled = voiceStatus && voiceStatus.ok === false

  // Tell the shell (cosmic canvas pulse) when the Master Brain is working.
  useEffect(() => {
    if (typeof onBusyChange === 'function') onBusyChange(streaming)
  }, [streaming, onBusyChange])

  // ── Composer auto-grow ────────────────────────────────────────────────────

  useEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`
  }, [input])

  const engineLine = engine && engine.ok
    ? `Engine: ${engine.model}`
    : engine && engine.error
      ? `Engine check failed: ${engine.error}`
      : 'Checking engine…'

  const filteredSessions = useMemo(() => {
    const q = sessionFilter.trim().toLowerCase()
    if (!q) return sessions
    return sessions.filter((s) => String(s.title || 'New chat').toLowerCase().includes(q))
  }, [sessions, sessionFilter])

  const saveRename = useCallback(async (sid) => {
    const title = renameDraft.trim()
    setRenamingId('')
    if (!title) return
    try {
      const out = await chatApi.patchSession(sid, { title })
      setSessions((prev) => prev.map((s) => (s.id === sid ? { ...s, title: out.title } : s)))
    } catch { /* rename is cosmetic; ignore transport failure */ }
  }, [renameDraft])

  const copyText = useCallback((text) => {
    try { navigator.clipboard.writeText(text || '') } catch { /* clipboard blocked */ }
  }, [])

  return (
    <div className={`chat-shell ${railOpen ? 'rail-open' : 'rail-hidden'}`}>
      <aside className="chat-rail" aria-label="Chat sessions" data-testid="chat-rail">
        <div className="chat-rail-head">
          <button type="button" className="btn btn-sm" onClick={newChat} data-testid="chat-new">
            <Icon name="plus" size={13} /> New chat
          </button>
          <button type="button" className="btn btn-sm btn-ghost" aria-label="Hide sessions"
            onClick={() => setRailOpen(false)}>&lsaquo;</button>
        </div>
        <input
          type="search" className="chat-rail-search" value={sessionFilter}
          onChange={(e) => setSessionFilter(e.target.value)}
          placeholder="Search sessions…" aria-label="Search sessions"
        />
        <div className="chat-rail-list">
          {sessions.length === 0 && (
            <div className="chat-rail-empty">No sessions yet — say something to start.</div>
          )}
          {filteredSessions.map((s) => (
            <div key={s.id} className={`chat-rail-row ${s.id === activeId ? 'active' : ''}`}>
              {renamingId === s.id ? (
                <input
                  className="chat-rail-rename" value={renameDraft} autoFocus
                  onChange={(e) => setRenameDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') saveRename(s.id)
                    if (e.key === 'Escape') setRenamingId('')
                  }}
                  onBlur={() => saveRename(s.id)}
                  aria-label="Rename session"
                />
              ) : (
                <>
                  <button type="button" className="chat-rail-item"
                    onClick={() => loadSession(s.id)}>
                    {s.title || 'New chat'}
                    <span className="chat-rail-meta">{relTime(s.updated_at)}</span>
                  </button>
                  <button type="button" className="chat-rail-edit" aria-label="Rename session"
                    title="Rename"
                    onClick={() => { setRenamingId(s.id); setRenameDraft(s.title || '') }}>
                    ✎
                  </button>
                </>
              )}
            </div>
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
          <h2>{heading}</h2>
          <span className="chat-head-sub">
            {sub} &middot; <span className="chat-head-spark">{focus?.label || 'Auto'}</span>
          </span>
          <span style={{ flex: 1 }} />
          {onOpenAdvanced && (
            <button type="button" className="btn btn-sm btn-ghost"
              onClick={() => onOpenAdvanced('/home')}
              title="Open the room-based Advanced view" data-testid="chat-open-advanced">
              Advanced view
            </button>
          )}
          {streaming && !paused && (
            <button type="button" className="btn btn-sm" onClick={() => { stop(); setPaused(true) }}
              data-testid="chat-pause" title="Pause the agent and take over">
              ⏸ Pause
            </button>
          )}
          {paused && (
            <span className="chip mb-chip" data-testid="chat-paused" title="The agent is waiting for you">
              You&rsquo;re driving — agent paused
            </span>
          )}
          {paused && (
            <button type="button" className="btn btn-sm btn-ghost"
              onClick={() => setPaused(false)} data-testid="chat-resume">
              ▶ Resume agent
            </button>
          )}
          {streaming && (
            <button type="button" className="btn btn-sm" onClick={stop} data-testid="chat-stop">
              Stop
            </button>
          )}
        </div>
        {loadError && <div className="chat-hint">{loadError}</div>}

        <div className="chat-stream" ref={scrollRef} onScroll={onStreamScroll}
          data-testid="chat-stream" role="log" aria-live="polite" aria-busy={streaming}>
          {messages.length === 0 && (
            <div className="chat-empty">
              <div className="chat-empty-rule" />
              <h3>{focus?.id === 'create' ? 'What are we making?' : 'What are we working on?'}</h3>
              <p>
                {focus?.blurb || 'Ask the Master Brain anything about the operation.'}{' '}
                Answers stream here with their thinking shown, tool runs made visible, and
                every artifact saved to the studio.
              </p>
              <div className="chat-suggestions">
                {suggestions.map((s) => (
                  <button key={s} type="button" className="chat-suggestion"
                    onClick={() => send(s)}>
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
            const toolCount = (m.tools || []).length
            return (
              <div key={m.id}
                className={`chat-msg ${m.role} ${m.status === 'error' ? 'error' : ''}`}>
                {m.role === 'assistant' && toolCount > 0 && (
                  <div className="chat-tools" data-testid="chat-tools">
                    {m.tools.map((tj) => (
                      <div key={tj.call_id} className={`chat-tool ${tj.status}`}>
                        <span className="chat-tool-icon" aria-hidden="true">⚙</span>
                        <span className="chat-tool-name">{toolLabel(tj.name, tj.label)}</span>
                        <span className="chat-tool-state">
                          {tj.status === 'running'
                            ? [tj.pct != null ? `${tj.pct}%` : null, tj.label].filter(Boolean).join(' · ') || 'working…'
                            : tj.status === 'done' ? '✓ done' : '✗ failed'}
                        </span>
                        <span className="chat-tool-machine">{tj.name}</span>
                        {tj.status === 'running' && (
                          <span className="chat-tool-bar">
                            <i className={tj.pct != null ? '' : 'indet'}
                              style={tj.pct != null ? { width: `${tj.pct}%` } : undefined} />
                          </span>
                        )}
                        {tj.status === 'done' && tj.summary && (
                          <details className="chat-tool-detail">
                            <summary>details</summary>
                            {tj.args && <div className="chat-tool-args">{String(tj.args).slice(0, 600)}</div>}
                            <div>{tj.summary}</div>
                          </details>
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
                      <div key={`${a.id}-${i}`} className="chat-asset-card">
                        {(!a.kind || a.kind === 'image') && (
                          <img src={assetFileUrl(a.id)} alt={a.name || 'generated asset'}
                            loading="lazy" onClick={() => setLightbox(a)} />
                        )}
                        {a.kind === 'dieline' && (
                          <object data={assetFileUrl(a.id)} type="image/svg+xml"
                            className="chat-asset-dieline" aria-label={a.name || 'dieline'}>
                            <span className="chat-asset-meta">{a.name || 'dieline'}</span>
                          </object>
                        )}
                        {a.kind === 'video' && (
                          <video src={assetFileUrl(a.id)} controls preload="metadata" />
                        )}
                        <span className="chat-asset-meta">
                          {a.name || 'asset'}
                          {a.width && a.height ? ` · ${a.width}×${a.height}` : ''}
                        </span>
                        <span className="chat-asset-actions">
                          {(!a.kind || a.kind === 'image') && (
                            <button type="button" onClick={() => setLightbox(a)}>View</button>
                          )}
                          <a href={assetFileUrl(a.id)} download>Download</a>
                          <button type="button" onClick={() => copyText(a.id)}>Copy id</button>
                          {onOpenAdvanced && (
                            <button type="button" title="Open the Advanced studio to composite this"
                              onClick={() => onOpenAdvanced('/design-studio')}>
                              Open in studio
                            </button>
                          )}
                        </span>
                      </div>
                    ) : null))}
                  </div>
                )}
                {m.role === 'assistant' && (m.cards || []).length > 0 && (
                  <div className="chat-cards" data-testid="chat-cards">
                    {m.cards.map((c) => (
                      <div key={c.id} className={`chat-card ${c.ok ? '' : 'error'}`}>
                        <div className="chat-card-title">{c.title}</div>
                        {(c.rows || []).map((r, i) => (
                          <div key={i} className="chat-card-row">
                            <span className="chat-card-label">{r.label}</span>
                            <span className="chat-card-value">{r.value}</span>
                          </div>
                        ))}
                        {c.action && (
                          <button type="button" className="btn btn-sm"
                            onClick={() => send(c.action.message)}
                            data-testid="chat-card-action">
                            {c.action.label || 'Open'}
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                {m.role === 'assistant' && m.thinking && (
                  <details className="chat-thinking" open={m.status === 'streaming'}>
                    <summary>
                      <span className="chat-spark" />
                      {m.status === 'streaming'
                        ? 'Thinking…'
                        : `Thought${seconds ? ` for ${seconds}s` : ''} · ${m.thinking.length} chars`}
                    </summary>
                    <div className="chat-thinking-body">{m.thinking}</div>
                  </details>
                )}
                {m.role === 'user' && editing && editing.id === m.id ? (
                  <div className="chat-edit-box">
                    <textarea value={editing.text} autoFocus
                      onChange={(e) => setEditing({ ...editing, text: e.target.value })}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(editing.text) }
                        if (e.key === 'Escape') setEditing(null)
                      }}
                      aria-label="Edit message" />
                    <div className="chat-edit-actions">
                      <button type="button" className="btn btn-sm btn-primary"
                        onClick={() => send(editing.text)}>Send as new turn</button>
                      <button type="button" className="btn btn-sm btn-ghost"
                        onClick={() => setEditing(null)}>Cancel</button>
                    </div>
                  </div>
                ) : (
                  m.content && (
                    <div className="chat-bubble">
                      {m.role === 'assistant' ? <RichText text={m.content} /> : m.content}
                    </div>
                  )
                )}
                {!m.content && m.status === 'streaming' && (
                  <div className="chat-bubble"><span className="chat-caret" /></div>
                )}
                {(m.notices || []).length > 0 && (
                  <div className="chat-hint" data-testid="chat-notices">
                    {m.notices.join(' · ')}
                  </div>
                )}
                {m.status === 'error' && (
                  <div className="chat-hint">
                    Error: {m.error || 'unknown'} — nothing was fabricated.
                    {m.prompt && (
                      <>
                        {' '}
                        <button type="button" className="btn btn-sm"
                          onClick={() => send(m.prompt)}>Retry</button>
                      </>
                    )}
                  </div>
                )}
                {m.status === 'cancelled' && (
                  <div className="chat-hint">
                    Stopped — the partial answer was saved as partial.
                    {m.prompt && (
                      <>
                        {' '}
                        <button type="button" className="btn btn-sm"
                          onClick={() => send(m.prompt)}>Continue from a new turn</button>
                      </>
                    )}
                  </div>
                )}
                {m.role === 'assistant' && m.status !== 'streaming' && m.content && (
                  <div className="chat-receipt">
                    <span className="chip">{focus?.label || 'Auto'} focus</span>
                    {m.model && <span className="chip">{m.model}</span>}
                    {toolCount > 0 && <span className="chip">{toolCount} tool run{toolCount > 1 ? 's' : ''}</span>}
                    {seconds && <span className="chip">{seconds}s</span>}
                    <button type="button" className="chat-msg-copy" data-testid="chat-fork"
                      title="Branch a new chat from this point — the original is untouched"
                      onClick={() => forkFrom(m.id)}>Fork</button>
                    <button type="button" className="chat-msg-copy"
                      onClick={() => copyText(m.content)}>Copy</button>
                  </div>
                )}
                {m.role === 'user' && !editing && (
                  <div className="chat-msg-tools">
                    <button type="button" className="chat-msg-copy"
                      onClick={() => setEditing({ id: m.id, text: m.content })}>Edit & resend</button>
                    <button type="button" className="chat-msg-copy" data-testid="chat-fork"
                      title="Branch a new chat from this point — the original is untouched"
                      onClick={() => forkFrom(m.id)}>Fork</button>
                    <button type="button" className="chat-msg-copy"
                      onClick={() => copyText(m.content)}>Copy</button>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {!pinned && streaming && (
          <button type="button" className="chat-jump"
            onClick={() => { setPinned(true); const el = scrollRef.current; if (el) el.scrollTop = el.scrollHeight }}>
            Jump to latest ↓
          </button>
        )}

        <div className="chat-composer">
          {queue.length > 0 && (
            <div className="chat-queue-list" data-testid="chat-queue">
              {queue.map((q, i) => (
                <span key={`${q}-${i}`} className="chat-queue-chip">
                  {q.slice(0, 48)}{q.length > 48 ? '…' : ''}
                  <button type="button" aria-label="Remove queued message"
                    onClick={() => setQueue((prev) => prev.filter((_, idx) => idx !== i))}>×</button>
                </span>
              ))}
              <button type="button" className="chat-msg-copy" onClick={() => setQueue([])}>
                clear
              </button>
            </div>
          )}
          <div className="chat-composer-box">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  send()
                }
              }}
              placeholder={streaming
                ? 'Type — it queues and sends next…'
                : `Ask the Master Brain (${focus?.label || 'Auto'} focus)…`}
              rows={1}
              aria-label="Chat message"
              data-testid="chat-input"
            />
            {recording ? (
              <button type="button" className="btn btn-sm btn-danger" onClick={stopRecording}
                data-testid="chat-voice-stop" aria-label="Stop recording">
                ■ {recordSeconds}s — stop
              </button>
            ) : (
              <button type="button" className="btn btn-sm" onClick={startRecording}
                disabled={transcribing || !!voiceDisabled} data-testid="chat-voice"
                title={voiceDisabled
                  ? `Voice unavailable: ${voiceStatus.detail || 'whisper not found'}`
                  : 'Push-to-talk (local whisper.cpp)'}
                aria-label="Record voice message">
                {transcribing ? 'Transcribing…' : '● Voice'}
              </button>
            )}
            <button type="button" className="btn btn-primary btn-sm" onClick={() => send()}
              disabled={!input.trim()} data-testid="chat-send" aria-label="Send">
              Send
            </button>
          </div>
          <div className="chat-hint">
            {voiceNote && <span className="chat-voice-note">{voiceNote} · </span>}
            Enter sends · Shift+Enter newline · Stop saves the partial as partial ·
            Voice records locally and transcribes with whisper.cpp (no audio leaves this machine).
          </div>
        </div>
      </section>

      {lightbox && (
        <div className="chat-lightbox" onClick={() => setLightbox(null)}
          role="dialog" aria-label="Asset preview" data-theme-scope="media">
          <div className="chat-lightbox-body" onClick={(e) => e.stopPropagation()}>
            <img src={assetFileUrl(lightbox.id)} alt={lightbox.name || 'asset'} />
            <div className="chat-lightbox-bar">
              <span>{lightbox.name || 'asset'}</span>
              <a href={assetFileUrl(lightbox.id)} download>Download</a>
              <button type="button" onClick={() => copyText(lightbox.id)}>Copy id</button>
              <button type="button" onClick={() => setLightbox(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
