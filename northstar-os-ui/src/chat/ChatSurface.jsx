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
import WorkbenchPanel from './WorkbenchPanel.jsx'
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

// A plan card's action becomes a precise instruction the brain can act on with the
// creative_plan tool (it needs the plan_id to find the plan again).
function planMessage(card, option) {
  const base = `Plan ${card.planId}:`
  if (option.id === 'draft') return `${base} generate the first draft now.`
  if (option.id === 'final') return `${base} generate the final now.`
  if (option.id === 'edit') return `${base} I want to edit the plan - ask me what to change.`
  return `${base} cancel it.`
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
  // Local models emit `*emphasis*` as well as `**strong**`; without the single
  // asterisk branch the prompt's own italics leak into the prose as literal
  // punctuation. Bold is matched first so `**x**` never parses as `*` + `*x*`.
  const re = /(\*\*[^*]+\*\*|\*[^*\n]+\*|`[^`]+`|\[[^\]]+\]\((https?:\/\/[^\s)]+)\)|https?:\/\/[^\s<>)]+)/g
  let last = 0
  let m
  let i = 0
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index))
    const tok = m[0]
    if (tok.startsWith('**')) {
      out.push(<strong key={`${keyPrefix}-b${i}`}>{tok.slice(2, -2)}</strong>)
    } else if (tok.startsWith('*')) {
      out.push(<em key={`${keyPrefix}-i${i}`}>{tok.slice(1, -1)}</em>)
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
  const [workbenchOpen, setWorkbenchOpen] = useState(false)  // V3 S5 AutothinK panel
  // Bojo composer options (turn contract v2). They travel with the turn and are
  // never written into the operator's message.
  const [media, setMedia] = useState('image')
  const [thinking, setThinking] = useState('standard')
  // Task posture: creative diverges, standard answers, thinking verifies.
  // Server-owned contract (chat_router._MODE_CONTRACT) — the client only picks.
  const [mode, setMode] = useState('standard')
  const [style, setStyle] = useState('balanced')
  const [attachments, setAttachments] = useState([])
  const [uploading, setUploading] = useState(false)
  const [uploadNote, setUploadNote] = useState('')
  const fileRef = useRef(null)
  // Duplex voice: listen -> transcribe -> answer -> speak, with barge-in.
  const [voices, setVoices] = useState([])
  const [voiceId, setVoiceId] = useState('bojo-narrator')
  const [conversation, setConversation] = useState(false)
  const [voiceState, setVoiceState] = useState('idle')   // idle|listening|thinking|speaking
  // Per-message rating. This is the improvement loop's strongest signal: a
  // thumbs-down becomes a gap in the nightly cycle. Best-effort by design —
  // a failed rating must never disturb the conversation.
  const [ratings, setRatings] = useState({})
  const convRef = useRef(null)                            // {stream, ctx, analyser, rec, audio, cancelled}
  const voiceStateRef = useRef('idle')
  voiceStateRef.current = voiceState
  // Always-current message list, so the loop can tell a NEW answer from history.
  const messagesRef = useRef(messages)
  messagesRef.current = messages
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
            // Bojo's generation plan: options carry their own credit cost.
            kind: p.kind || '',
            planId: p.plan_id || '',
            options: Array.isArray(p.options) ? p.options : [],
            steps: Array.isArray(p.steps) ? p.steps : [],
            job: p.job || '',
            media: p.media || '',
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
      await streamTurn(sid, {
        content,
        think: thinking !== 'off',
        media,
        thinking,
        mode,
        style,
        attachments: attachments.map((a) => a.id),
      }, ({ event, data }) => {
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

  // The voice list comes from the (external) voice engine. Offline is a normal
  // state: the picker stays visible, disabled, and says why.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const r = await fetch('/api/chat/voice/voices', { credentials: 'include' })
        if (!r.ok) return
        const d = await r.json()
        if (!cancelled && Array.isArray(d.voices)) setVoices(d.voices)
      } catch { /* engine offline: the default voice stays selected */ }
    })()
    return () => { cancelled = true }
  }, [])

  // Tell the shell (cosmic canvas pulse) when the Master Brain is working.
  useEffect(() => {
    if (typeof onBusyChange === 'function') onBusyChange(streaming)
  }, [streaming, onBusyChange])

  // In conversation mode, a finished turn is spoken and the loop keeps listening.
  // Only a message that arrived AFTER the loop started is spoken: enabling Talk
  // must never blurt out the previous conversation's last answer.
  useEffect(() => {
    if (!conversation || streaming) return
    const c = convRef.current
    if (!c) return
    const last = [...messages].reverse().find((m) => m.role === 'assistant' && m.content)
    if (!last || last.id === c.seenMsgId) return
    c.seenMsgId = last.id
    speak(last.content)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [streaming, conversation])

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

  const rate = useCallback(async (m, verdict) => {
    setRatings((r) => ({ ...r, [m.id]: verdict }))
    try {
      await fetch('/api/v1/improvement/feedback', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          verdict,
          message_id: String(m.id || ''),
          session_id: String(activeId || ''),
          note: verdict === 'down' ? String(m.content || '').slice(0, 600) : '',
          mode: 'standard',
          pack_version: '',
        }),
      })
    } catch { /* rating is best-effort; the answer stands */ }
  }, [activeId])

  const copyText = useCallback((text) => {
    try { navigator.clipboard.writeText(text || '') } catch { /* clipboard blocked */ }
  }, [])

  // Upload an operator attachment through the design-studio asset route. Cookie
  // auth needs the CSRF double-submit header, exactly like foundation/api.js.
  const uploadFile = useCallback(async (file) => {
    if (!file) return
    setUploading(true)
    setUploadNote('')
    try {
      const m = document.cookie.match(/(^|;)\s*ns_csrf\s*=\s*([^;]+)/)
      const csrf = m ? decodeURIComponent(m[2]) : ''
      const fd = new FormData()
      fd.append('file', file)
      const res = await fetch('/api/design-studio/assets/upload', {
        method: 'POST', credentials: 'include', body: fd,
        headers: csrf ? { 'X-CSRF-Token': csrf } : {},
      })
      if (!res.ok) {
        let detail = ''
        try { const b = await res.json(); detail = typeof b.detail === 'string' ? b.detail : '' } catch { /* no body */ }
        throw new Error(detail || `HTTP ${res.status}`)
      }
      const out = await res.json()
      setAttachments((prev) => [...prev, {
        id: out.id, name: (out.asset && out.asset.name) || file.name,
      }])
    } catch (e) {
      setUploadNote(`Upload failed: ${e.message}`)
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }, [])

  // ── Duplex voice loop (Bojo) ──────────────────────────────────────────────
  // listen (energy VAD) -> local whisper transcript -> turn -> speak (voice
  // studio) -> listen again. Speaking while the operator talks BARGE-IN: the
  // audio stops and capture resumes. Every unavailable piece is reported, never
  // faked.
  const stopConversation = useCallback(() => {
    const c = convRef.current
    if (c) {
      c.cancelled = true
      try { if (c.rec && c.rec.state !== 'inactive') c.rec.stop() } catch { /* already stopped */ }
      try { if (c.audio) { c.audio.pause(); c.audio.src = '' } } catch { /* no audio */ }
      try { if (c.stream) c.stream.getTracks().forEach((t) => t.stop()) } catch { /* no stream */ }
      try { if (c.ctx && c.ctx.state !== 'closed') c.ctx.close() } catch { /* no ctx */ }
    }
    convRef.current = null
    setConversation(false)
    setVoiceState('idle')
  }, [])

  const speak = useCallback(async (text) => {
    const c = convRef.current
    if (!c || c.cancelled || !text) return
    setVoiceState('speaking')
    try {
      const csrfMatch = document.cookie.match(/(^|;)\s*ns_csrf\s*=\s*([^;]+)/)
      const res = await fetch('/api/chat/voice/speak', {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json',
                   ...(csrfMatch ? { 'X-CSRF-Token': decodeURIComponent(csrfMatch[2]) } : {}) },
        body: JSON.stringify({ text: text.slice(0, 1200), voice_id: voiceId }),
      })
      if (!res.ok) {
        const b = await res.json().catch(() => ({}))
        const detail = typeof b.detail === 'string' ? b.detail : 'voice unavailable'
        setVoiceNote(`Bojo can't speak right now: ${detail}`)
        setVoiceState('idle')
        return
      }
      const { audio_url: url } = await res.json()
      const audio = new Audio(url)
      c.audio = audio
      audio.onended = () => { if (convRef.current && !convRef.current.cancelled) setVoiceState('idle') }
      // Barge-in: if the operator starts talking, stop Bojo mid-sentence.
      const watch = setInterval(() => {
        if (!convRef.current || convRef.current.cancelled) { clearInterval(watch); return }
        if (energy() > 0.05) {
          clearInterval(watch)
          try { audio.pause() } catch { /* ignore */ }
          setVoiceState('listening')
          listenOnce()
        }
      }, 120)
      await audio.play().catch(() => { setVoiceState('idle') })
    } catch (e) {
      setVoiceNote(`Bojo can't speak right now: ${e.message}`)
      setVoiceState('idle')
    }
  }, [])

  function energy() {
    const c = convRef.current
    if (!c || !c.analyser) return 0
    const buf = new Uint8Array(c.analyser.fftSize)
    c.analyser.getByteTimeDomainData(buf)
    let sum = 0
    for (let i = 0; i < buf.length; i += 1) {
      const v = (buf[i] - 128) / 128
      sum += v * v
    }
    return Math.sqrt(sum / buf.length)
  }

  async function listenOnce() {
    const c = convRef.current
    if (!c || c.cancelled) return
    setVoiceState('listening')
    const rec = new MediaRecorder(c.stream)
    c.rec = rec
    const chunks = []
    rec.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data) }
    rec.onstop = async () => {
      if (!convRef.current || convRef.current.cancelled) return
      setVoiceState('thinking')
      const blob = new Blob(chunks, { type: rec.mimeType || 'audio/webm' })
      if (!blob.size) { listenOnce(); return }
      try {
        const csrfMatch = document.cookie.match(/(^|;)\s*ns_csrf\s*=\s*([^;]+)/)
        const fd = new FormData()
        fd.append('audio', blob, 'turn.webm')
        const res = await fetch('/api/chat/voice/transcribe', {
          method: 'POST', credentials: 'include', body: fd,
          headers: csrfMatch ? { 'X-CSRF-Token': decodeURIComponent(csrfMatch[2]) } : {},
        })
        const out = await res.json().catch(() => ({}))
        if (!res.ok) {
          setVoiceNote(`Transcription unavailable: ${typeof out.detail === 'string' ? out.detail : res.status}`)
          setVoiceState('idle')
          return
        }
        const text = String(out.text || '').trim()
        if (text) send(text)
        else setVoiceState('listening')
      } catch (e) {
        setVoiceNote(`Transcription failed: ${e.message}`)
        setVoiceState('idle')
      }
    }
    rec.start()
    // Simple energy VAD: stop after speech followed by ~900 ms of quiet, or 15 s.
    let heard = false
    let quiet = 0
    const t0 = Date.now()
    const tick = setInterval(() => {
      if (!convRef.current || convRef.current.cancelled) { clearInterval(tick); return }
      const e = energy()
      if (e > 0.05) { heard = true; quiet = 0 } else if (heard) { quiet += 1 }
      const tooLong = Date.now() - t0 > 15000
      if ((heard && quiet >= 6) || tooLong) {
        clearInterval(tick)
        try { if (rec.state !== 'inactive') rec.stop() } catch { /* ignore */ }
      }
    }, 150)
  }

  const startConversation = useCallback(async () => {
    setVoiceNote('')
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      setVoiceNote('This browser cannot capture audio for a live conversation.')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const ctx = new (window.AudioContext || window.webkitAudioContext)()
      const source = ctx.createMediaStreamSource(stream)
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 1024
      source.connect(analyser)
      convRef.current = { stream, ctx, analyser, audio: null, rec: null, cancelled: false }
      const lastAssistant = [...messagesRef.current].reverse()
        .find((m) => m.role === 'assistant' && m.content)
      convRef.current.seenMsgId = lastAssistant ? lastAssistant.id : ''
      setConversation(true)
      listenOnce()
    } catch (e) {
      setVoiceNote(`Microphone unavailable: ${e.message}`)
    }
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
          <button type="button" className="btn btn-sm btn-ghost"
            onClick={() => setWorkbenchOpen((v) => !v)}
            title="Plan, artifacts and runs for this session"
            aria-pressed={workbenchOpen} data-testid="chat-workbench-toggle">
            ⌥ Workbench
          </button>
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
                      <div key={c.id} className={`chat-card ${c.ok ? '' : 'error'} ${c.kind === 'generation_plan' ? 'chat-card-plan' : ''}`}>
                        <div className="chat-card-title">{c.title}</div>
                        {(c.rows || []).map((r, i) => (
                          <div key={i} className="chat-card-row">
                            <span className="chat-card-label">{r.label}</span>
                            <span className="chat-card-value">{r.value}</span>
                          </div>
                        ))}
                        {c.kind === 'generation_plan' && (c.options || []).length > 0 && (
                          <div className="chat-plan-actions">
                            {c.options.map((o) => (
                              <button key={o.id} type="button"
                                className={`chat-plan-btn ${o.id === 'final' ? 'is-primary' : ''} ${o.enabled === false ? 'is-disabled' : ''}`}
                                disabled={o.enabled === false}
                                title={o.note || ''}
                                onClick={() => send(planMessage(c, o))}
                                data-testid={`chat-plan-${o.id}`}>
                                <span className="chat-plan-btn-label">{o.label}</span>
                                {o.credits > 0 && (
                                  <span className="chat-plan-btn-cost">{o.credits} cr</span>
                                )}
                              </button>
                            ))}
                          </div>
                        )}
                        {(c.steps || []).length > 0 && (
                          <details className="chat-plan-steps">
                            <summary>{c.steps.length} planned steps</summary>
                            <ol>
                              {c.steps.map((s, i) => (
                                <li key={i}>
                                  {s.what} <code>{s.tool}</code>
                                  {s.available === false && <span className="chat-plan-gap"> (pipeline)</span>}
                                </li>
                              ))}
                            </ol>
                          </details>
                        )}
                        {c.action && c.kind !== 'generation_plan' && (
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
                    <button type="button" className="chat-msg-copy"
                      data-testid="rate-up"
                      title="This answer was right — record it"
                      onClick={() => rate(m, 'up')}>
                      {ratings[m.id] === 'up' ? 'Rated right' : 'Right'}
                    </button>
                    <button type="button" className="chat-msg-copy"
                      data-testid="rate-down"
                      title="This answer was wrong — it becomes a gap the loop researches"
                      onClick={() => rate(m, 'down')}>
                      {ratings[m.id] === 'down' ? 'Gap recorded' : 'Wrong'}
                    </button>
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
          <div className="chat-controls">
            <div className="chat-media-toggle" role="tablist" aria-label="Output media">
              {['image', 'video'].map((m) => (
                <button key={m} type="button" role="tab" aria-selected={media === m}
                  className={`chat-media-opt ${media === m ? 'is-on' : ''}`}
                  onClick={() => setMedia(m)} data-testid={`chat-media-${m}`}>
                  {m === 'image' ? 'Image' : 'Video'}
                </button>
              ))}
            </div>
            <label className="chat-control">
              <span>Voice</span>
              <select value={voiceId} onChange={(e) => setVoiceId(e.target.value)}
                disabled={voices.length === 0}
                title={voices.length ? '' : 'Voice engine offline (127.0.0.1:8321)'}
                data-testid="chat-voice">
                {voices.length === 0 && <option value={voiceId}>Bojo (engine offline)</option>}
                {voices.map((v) => {
                  const id = v.id || v.voice_id || v.name
                  return <option key={id} value={id}>{v.name || id}</option>
                })}
              </select>
            </label>
            <label className="chat-control">
              <span>Mode</span>
              <select value={mode} onChange={(e) => setMode(e.target.value)}
                data-testid="chat-mode"
                title="Creative diverges, standard answers, thinking verifies">
                <option value="creative">Creative</option>
                <option value="standard">Standard</option>
                <option value="thinking">Thinking</option>
              </select>
            </label>
            <label className="chat-control">
              <span>Thinking</span>
              <select value={thinking} onChange={(e) => setThinking(e.target.value)}
                data-testid="chat-thinking">
                <option value="off">Off</option>
                <option value="standard">Standard</option>
                <option value="deep">Deep</option>
              </select>
            </label>
            <label className="chat-control">
              <span>Style</span>
              <select value={style} onChange={(e) => setStyle(e.target.value)}
                data-testid="chat-style">
                <option value="concise">Concise</option>
                <option value="balanced">Balanced</option>
                <option value="detailed">Detailed</option>
              </select>
            </label>
            <button type="button" className="chat-icon-btn" title="Attach a file"
              onClick={() => fileRef.current?.click()} disabled={uploading}
              data-testid="chat-attach" aria-label="Attach a file">
              {uploading ? '…' : '📎'}
            </button>
            <button type="button"
              className={`chat-icon-btn ${conversation ? 'is-live' : ''}`}
              title={conversation ? 'End the live conversation' : 'Talk to Bojo (live voice)'}
              onClick={() => (conversation ? stopConversation() : startConversation())}
              aria-pressed={conversation} data-testid="chat-conversation">
              {conversation
                ? (voiceState === 'speaking' ? '🔊' : voiceState === 'thinking' ? '…' : '●')
                : '🎙'}
            </button>
            <input ref={fileRef} type="file" hidden
              accept="image/*,video/*,application/pdf,text/plain,text/csv"
              onChange={(e) => uploadFile(e.target.files && e.target.files[0])}
              data-testid="chat-file" />
          </div>
          {attachments.length > 0 && (
            <div className="chat-attachments" data-testid="chat-attachments">
              {attachments.map((a) => (
                <span key={a.id} className="chat-attachment">
                  {a.name}
                  <button type="button" aria-label={`Remove ${a.name}`}
                    onClick={() => setAttachments((prev) => prev.filter((x) => x.id !== a.id))}>
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
          {uploadNote && <div className="chat-hint">{uploadNote}</div>}
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

      <WorkbenchPanel
        open={workbenchOpen}
        onClose={() => setWorkbenchOpen(false)}
        sessionId={activeId}
        focusId={focusId}
      />

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
