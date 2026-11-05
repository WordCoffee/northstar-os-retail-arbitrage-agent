// ═══════════════════════════════════════════════════════════════════════════
// CHAT SURFACE (V3) — the universal Master Brain chat.
//
// One component backs every Northstar surface:
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
import { useAssetSrc, saveAsset } from './assetUrl.js'
import { useWorkspaceOptional } from '../shell/WorkspaceTabs.jsx'

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
  apply_label: 'Putting the logo and copy on the pack',
  seo_check: 'Checking the latest listing revision',
}

// Machine name shown next to a run. The raw tool id was leaking into the UI as
// jargon; these are the same identifiers, written the way an operator reads them.
const TOOL_MACHINE = {
  system_status: 'engine',
  list_templates: 'print',
  design_brief: 'brief',
  create_dieline: 'print',
  generate_image: 'comfyui',
  apply_label: 'compositor',
  seo_check: 'seo',
}

// The service that ACTUALLY executes a tool, in product language, for the dock
// that appears while a run is live. Naming the service is the point: "working…"
// teaches the operator nothing.
const TOOL_SERVICE = {
  system_status: 'Local engine',
  list_templates: 'Dieline templates',
  design_brief: 'Brief builder',
  create_dieline: 'Dieline builder',
  generate_image: 'ComfyUI',
  apply_label: 'Label compositor',
  seo_check: 'SEO check',
}

// Live voice conversation (continuous listen → answer → speak) is a FUTURE
// feature. Dictation is real today; spoken replies are optional. The UI must
// never imply a live conversation is running, so the duplex loop stays behind
// this flag until streaming voice ships.
const LIVE_VOICE_ENABLED = false

// ── Asset media ────────────────────────────────────────────────────────────
// A generated artifact can be absent for different reasons, and collapsing them
// into one broken thumbnail is how "the image is missing" becomes folklore. The
// server reports `state` (missing_asset / missing_metadata / missing_file / ok);
// this renders exactly that, and an image that simply fails to decode gets its
// own honest note. It never retries, so a 404 cannot become a request loop.
function AssetImage({ assetId, alt, ...rest }) {
  const src = useAssetSrc(assetId)
  return <img src={src || undefined} alt={alt} {...rest} />
}

function AssetMedia({ asset, onOpen }) {
  const [failed, setFailed] = useState(false)
  const src = useAssetSrc(asset.id)
  const state = asset.state || null
  const reason = state === 'missing_file'
    ? 'File missing — the asset record exists but the file is gone.'
    : state === 'missing_metadata'
      ? 'Not stored — this asset has no file to serve.'
      : state === 'missing_asset' || asset.present === false
        ? 'Not found — the asset record is gone.'
        : failed ? 'Unavailable — the file could not be loaded.' : ''
  if (reason) {
    return (
      <div className="chat-asset-missing" data-testid="chat-asset-missing" role="status">
        <span>{reason}</span>
        <span className="chat-asset-missing-id">asset {asset.id}</span>
      </div>
    )
  }
  if (asset.kind === 'video') {
    return <video src={src || undefined} controls preload="metadata"
      onError={() => setFailed(true)} data-testid="chat-asset-video" />
  }
  if (asset.kind === 'dieline') {
    return (
      <object data={src || undefined} type="image/svg+xml"
        className="chat-asset-dieline" aria-label={asset.name || 'dieline'}>
        <span className="chat-asset-meta">{asset.name || 'dieline'}</span>
      </object>
    )
  }
  return (
    <img src={src || undefined} alt={asset.name || 'generated asset'}
      loading="lazy" onClick={onOpen} onError={() => setFailed(true)} />
  )
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
          // Markdown tables were printed as raw pipes. Render them as a real
          // table when the block looks like one (header row + separator row).
          const isTable = lines.length >= 2
            && lines[0].trim().startsWith('|')
            && /^\s*\|?[\s:|-]*-{2,}[\s:|-]*\|?\s*$/.test(lines[1])
          if (isTable) {
            const cells = (ln) => ln.trim().replace(/^\|/, '').replace(/\|$/, '')
              .split('|').map((c) => c.trim())
            const header = cells(lines[0])
            const rows = lines.slice(2).filter((ln) => ln.trim().startsWith('|')).map(cells)
            return (
              <div key={`p-${bi}-${pi}`} className="chat-table-wrap">
                <table className="chat-table">
                  <thead>
                    <tr>{header.map((h, hi) => (
                      <th key={`th-${hi}`}><Inline text={h} keyPrefix={`th-${bi}-${pi}-${hi}`} /></th>
                    ))}</tr>
                  </thead>
                  <tbody>
                    {rows.map((r, ri) => (
                      <tr key={`tr-${ri}`}>{r.map((c, ci) => (
                        <td key={`td-${ci}`}><Inline text={c} keyPrefix={`td-${bi}-${pi}-${ri}-${ci}`} /></td>
                      ))}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          }
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
  sub = 'Standard view',
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
  // Composer v2: the six option dropdowns live behind one disclosure so the input
  // is the biggest thing on screen instead of the smallest.
  const [optionsOpen, setOptionsOpen] = useState(false)
  // Task posture: creative diverges, standard answers, thinking verifies.
  // Server-owned contract (chat_router._MODE_CONTRACT) — the client only picks.
  const [mode, setMode] = useState('standard')
  const [style, setStyle] = useState('balanced')
  const [attachments, setAttachments] = useState([])
  const [uploading, setUploading] = useState(false)
  const [uploadNote, setUploadNote] = useState('')
  const [assetPickerOpen, setAssetPickerOpen] = useState(false)
  const [studioAssets, setStudioAssets] = useState([])
  const [studioAssetsState, setStudioAssetsState] = useState('idle')
  const fileRef = useRef(null)
  // Duplex voice: listen -> transcribe -> answer -> speak, with barge-in.
  const [voices, setVoices] = useState([])
  const [voiceId, setVoiceId] = useState('bojo-narrator')
  const [conversation, setConversation] = useState(false)
  // Optional spoken replies: after a turn completes, read the answer aloud with
  // the local voice engine. This is NOT a live conversation and is not labeled
  // as one anywhere in the UI.
  const [speakReplies, setSpeakReplies] = useState(false)
  // One-shot completion mark. Set ONLY from a live turn that ended `done`, so a
  // reload can never replay a success animation for an old message.
  const [celebrateId, setCelebrateId] = useState('')
  const celebrateTimer = useRef(null)
  const [voiceState, setVoiceState] = useState('idle')   // idle|listening|thinking|speaking
  // Per-message rating. This is the improvement loop's strongest signal: a
  // thumbs-down becomes a gap in the nightly cycle. Best-effort by design —
  // a failed rating must never disturb the conversation.
  const [ratings, setRatings] = useState({})
  const [noteFor, setNoteFor] = useState('')
  const [noteText, setNoteText] = useState('')
  const convRef = useRef(null)                            // {stream, ctx, analyser, rec, audio, cancelled}
  const voiceStateRef = useRef('idle')
  voiceStateRef.current = voiceState
  // speak() is created once (it must not re-bind mid-conversation), so it reads
  // the current voice through a ref instead of a stale closure. The stale closure
  // was a second reason every turn sent the old default voice.
  const voiceIdRef = useRef(voiceId)
  voiceIdRef.current = voiceId
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
  // U8: the workbench publishes the open canvas and ONE command entry point.
  // Optional — on the standalone home there is no provider and no canvas.
  const workspace = useWorkspaceOptional()
  const workspaceRef = useRef(workspace)
  workspaceRef.current = workspace

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
            .flatMap((p) => {
              // Prefer the persisted descriptor (name/kind/size). Older turns only
              // stored bare ids, which is why a whole session used to reload as a
              // row of identical "asset" cards.
              const meta = Array.isArray(p.asset_meta) ? p.asset_meta : []
              const byId = new Map(meta.filter((a) => a && a.id).map((a) => [a.id, a]))
              return (p.assets || []).map((id) => {
                const m = byId.get(id) || {}
                return {
                  id,
                  name: m.name || p.label || 'asset',
                  kind: m.kind || '',
                  width: m.width || null,
                  height: m.height || null,
                }
              })
            }),
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
  //
  // This must fire ONCE per focus, not on every `sessions` update. `loadSession`
  // blanks `messages` and refills it, so re-running it on list churn (the mount
  // fetch, a new title, a fork) rebuilt the whole transcript underneath the
  // reader: artefact <img> elements remounted and decoded again, which showed up
  // as an image that reported naturalWidth 0 right after a refetch and as a
  // composer that never satisfied an actionability "stable" check.
  const resumedFocus = useRef('')
  useEffect(() => {
    if (resumedFocus.current === focusId) return
    let sid = ''
    try { sid = localStorage.getItem(sessionKey(focusId)) || '' } catch { /* storage */ }
    if (!sid && sessions.length) sid = sessions[0].id
    if (!sid) return
    resumedFocus.current = focusId
    loadSession(sid, { remember: false })
  }, [focusId, sessions, loadSession])

  // Auto-pin the stream only while the reader is at the bottom.
  useEffect(() => {
    const el = scrollRef.current
    if (!el || !pinned) return
    el.scrollTop = el.scrollHeight
  }, [messages, streaming, pinned])

  // Preview closes on Escape — a full-screen overlay with no keyboard exit traps
  // the operator in it.
  useEffect(() => {
    if (!lightbox) return undefined
    const onKey = (e) => { if (e.key === 'Escape') setLightbox(null) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [lightbox])

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

    // U8: a concrete instruction about the OPEN canvas is applied here, through
    // the workspace's one command entry point, instead of being sent to the
    // model. The parser only recognises a narrow grammar (set/scale/add/select/
    // swap); anything it does not understand returns recognised:false and falls
    // through to the normal turn, so a general question is never hijacked.
    const ws = workspaceRef.current
    if (ws && typeof ws.runCanvasCommand === 'function') {
      const applied = ws.runCanvasCommand(content)
      if (applied && applied.recognised) {
        const reply = applied.ok
          ? `${applied.summary || 'Done.'} Undo is in the canvas toolbar.`
          : applied.error
        setMessages((prev) => [
          ...prev,
          { id: `local-u-${startedAt}`, role: 'user', content, thinking: '', status: 'done' },
          { id: `local-a-${startedAt}`, role: 'assistant', content: reply, thinking: '',
            status: applied.ok ? 'done' : 'error', startedAt, endedAt: Date.now() },
        ])
        setPinned(true)
        return
      }
    }

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
        canvas: workspaceRef.current?.summary?.canvas || undefined,
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
          // U8: the model proposed a canvas edit and the backend confirmed the
          // canvas can satisfy it. The BROWSER performs the edit, through the
          // same command entry point the fast path uses.
          if (data.name === 'canvas_edit' && data.ok) {
            const ws2 = workspaceRef.current
            // Use the instruction the tool actually proposed, not the user's
            // sentence: the model may have rephrased it into a form the parser
            // understands. Falls back to the turn's own words.
            const call = (m.tools || []).find((tj) => tj.call_id === data.call_id)
            let instruction = content
            try {
              const args = typeof call?.args === 'string' ? JSON.parse(call.args) : call?.args
              if (args && typeof args.instruction === 'string' && args.instruction.trim()) {
                instruction = args.instruction
              }
            } catch { /* keep the user's sentence */ }
            const applied = ws2 && typeof ws2.runCanvasCommand === 'function'
              ? ws2.runCanvasCommand(instruction)
              : null
            if (applied && applied.recognised && applied.ok) {
              patchBot((m2) => ({
                ...m2,
                content: `${m2.content || ''}${m2.content ? '\n\n' : ''}${applied.summary}`.trim(),
              }))
            }
          }
        } else if (event === 'card') {
          // A card the server built without the model (e.g. the deterministic
          // creative-plan router). Same shape the transcript loader builds from
          // persisted parts, so live and reloaded views agree.
          patchBot((m) => ({
            ...m,
            cards: [...(m.cards || []), {
              id: `card-live-${data.plan_id || Date.now()}-${(m.cards || []).length}`,
              title: data.title || 'Card',
              rows: Array.isArray(data.rows) ? data.rows : [],
              action: data.action || null,
              ok: true,
              kind: data.kind || '',
              planId: data.plan_id || '',
              options: Array.isArray(data.options) ? data.options : [],
              steps: Array.isArray(data.steps) ? data.steps : [],
              job: data.job || '',
              media: data.media || '',
            }],
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
          // Completion mark: only a turn that actually finished cleanly earns
          // it, and only a LIVE turn (a reload never calls this path).
          if ((data.status || 'done') === 'done') {
            setCelebrateId(botId)
            if (celebrateTimer.current) clearTimeout(celebrateTimer.current)
            celebrateTimer.current = setTimeout(() => setCelebrateId(''), 1800)
          }
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

  // ── Spoken replies (optional, one answer at a time) ───────────────────────
  // Honest replacement for the "live voice" button: nothing listens in the
  // background, only a finished answer is read out, and it can be stopped.
  const spokenSeen = useRef('')
  const spokenAudio = useRef(null)

  const speakReply = useCallback(async (text) => {
    const clean = String(text || '').trim()
    if (!clean) return
    try {
      if (spokenAudio.current) { try { spokenAudio.current.pause() } catch { /* no audio */ } }
      const csrfMatch = document.cookie.match(/(^|;)\s*ns_csrf\s*=\s*([^;]+)/)
      const res = await fetch('/api/chat/voice/speak', {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json',
                   ...(csrfMatch ? { 'X-CSRF-Token': decodeURIComponent(csrfMatch[2]) } : {}) },
        body: JSON.stringify({ text: clean.slice(0, 1200), voice_id: voiceIdRef.current }),
      })
      if (!res.ok) {
        const b = await res.json().catch(() => ({}))
        const detail = typeof b.detail === 'string' ? b.detail : 'voice unavailable'
        setVoiceNote(`Spoken replies unavailable: ${detail}`)
        return
      }
      const body = await res.json()
      if (body.voice_id) setVoiceId((cur) => (cur === body.voice_id ? cur : body.voice_id))
      const audio = new Audio(body.audio_url)
      spokenAudio.current = audio
      await audio.play().catch(() => { setVoiceNote('The browser blocked audio playback.') })
    } catch (e) {
      setVoiceNote(`Spoken replies unavailable: ${e.message}`)
    }
  }, [])

  const toggleSpeakReplies = useCallback(() => {
    setSpeakReplies((on) => {
      const next = !on
      if (next) {
        // Enabling must never read out the previous answer; only messages that
        // finish AFTER the toggle is switched on are spoken.
        const last = [...messagesRef.current].reverse().find((m) => m.role === 'assistant' && m.content)
        spokenSeen.current = last ? last.id : ''
      } else {
        if (spokenAudio.current) {
          try { spokenAudio.current.pause() } catch { /* already stopped */ }
          spokenAudio.current = null
        }
      }
      return next
    })
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

  // The voice picker must never disagree with the voice that is actually sent.
  // It used to sit on a hardcoded 'bojo-narrator' while the <select> displayed
  // the engine's first real voice — so the UI showed "Microsoft Zira Desktop"
  // and every spoken turn died with `unknown voice 'bojo-narrator'`.
  useEffect(() => {
    if (!voices.length) return
    const ids = voices.map((v) => v.id || v.voice_id || v.name).filter(Boolean)
    if (!ids.length) return
    setVoiceId((current) => (ids.includes(current) ? current : ids[0]))
  }, [voices])

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

  // Spoken replies: when a turn finishes and the toggle is on, read the new
  // answer once. Keyed off the message id so a re-render cannot replay it.
  useEffect(() => {
    if (!speakReplies || streaming) return
    const last = [...messages].reverse().find((m) => m.role === 'assistant' && m.content)
    if (!last || last.id === spokenSeen.current) return
    spokenSeen.current = last.id
    speakReply(last.content)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages, streaming, speakReplies])

  // A spoken answer must stop when the surface goes away.
  useEffect(() => () => {
    if (spokenAudio.current) { try { spokenAudio.current.pause() } catch { /* no audio */ } }
    if (celebrateTimer.current) clearTimeout(celebrateTimer.current)
  }, [])

  // ── Composer auto-grow ────────────────────────────────────────────────────

  useEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`
  }, [input])

  const engineLine = engine && engine.ok
    ? `Engine: ${engine.model}`
      + (engine.tools?.length ? ` · ${engine.tools.length} skills` : '')
      + (engine.services?.length ? ` across ${engine.services.length} services` : '')
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

  const rate = useCallback(async (m, verdict, note = '') => {
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
          // The operator's own words when given, otherwise the answer itself as
          // evidence for the nightly gap review.
          note: String(note || (verdict === 'down' ? String(m.content || '') : '')).slice(0, 600),
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

  // ── Existing-asset picker ─────────────────────────────────────────────────
  // Lists the studio's own asset registry so an approved brand asset can be
  // attached by id. This is the automation-drivable equivalent of the paperclip:
  // no native file dialog, and the tool still receives a real asset id.
  const loadStudioAssets = useCallback(async () => {
    setStudioAssetsState('loading')
    try {
      const res = await fetch('/api/design-studio/assets', { credentials: 'same-origin' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const body = await res.json()
      const list = Array.isArray(body.assets) ? body.assets : []
      // Newest first; logos first so a brand asset is never buried under renders.
      list.sort((a, b) => {
        const rank = (x) => (String(x.asset_type || '').match(/logo|brand/i) ? 0 : 1)
        return rank(a) - rank(b) || String(b.created_at || '').localeCompare(String(a.created_at || ''))
      })
      setStudioAssets(list)
      setStudioAssetsState(list.length ? 'ready' : 'empty')
    } catch (e) {
      setStudioAssetsState('error')
      setUploadNote(`Asset library unavailable: ${e.message}`)
    }
  }, [])

  const attachExistingAsset = useCallback((asset) => {
    const id = String(asset.id || '')
    if (!id) return
    setAttachments((prev) => (prev.some((a) => a.id === id) ? prev : [...prev, {
      id,
      name: asset.name || id,
      kind: asset.asset_type || 'image',
    }]))
    setAssetPickerOpen(false)
  }, [])

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
        body: JSON.stringify({ text: text.slice(0, 1200), voice_id: voiceIdRef.current }),
      })
      if (!res.ok) {
        const b = await res.json().catch(() => ({}))
        const detail = typeof b.detail === 'string' ? b.detail : 'voice unavailable'
        setVoiceNote(`Bojo can't speak right now: ${detail}`)
        setVoiceState('idle')
        return
      }
      const body = await res.json()
      // The server resolves an unknown/stale voice to a real one; keep the picker
      // honest about which voice is actually being used.
      if (body.voice_id) setVoiceId((cur) => (cur === body.voice_id ? cur : body.voice_id))
      setVoiceNote('')
      const audio = new Audio(body.audio_url)
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
    // Energy VAD: stop after speech followed by ~900 ms of quiet, or 15 s.
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
          <button type="button" className="chat-rail-toggle" aria-label="Hide sessions"
            title="Hide sessions"
            onClick={() => setRailOpen(false)}><Icon name="arrowLeft" size={15} /></button>
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
                    <Icon name="edit" size={13} />
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
            <button type="button" className="chat-rail-toggle" aria-label="Show sessions"
              title="Show sessions"
              onClick={() => setRailOpen(true)}><Icon name="menu" size={15} /></button>
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
            <Icon name="workflow" size={14} /> Workbench
          </button>
          {onOpenAdvanced && (
            <button type="button" className="btn btn-sm btn-ghost"
              onClick={() => onOpenAdvanced('/home')}
              title="Open the room-based Advanced view" data-testid="chat-open-advanced">
              <Icon name="grid" size={14} /> Advanced view
            </button>
          )}
          {streaming && !paused && (
            <button type="button" className="btn btn-sm" onClick={() => { stop(); setPaused(true) }}
              data-testid="chat-pause" title="Pause the agent and take over">
              <Icon name="clock" size={14} /> Pause
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
              <Icon name="refresh" size={14} /> Resume agent
            </button>
          )}
          {streaming && (
            <button type="button" className="btn btn-sm" onClick={stop} data-testid="chat-stop">
              <Icon name="x" size={14} /> Stop
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
            const runningTool = [...(m.tools || [])].reverse().find((t) => t.status === 'running')
            return (
              <div key={m.id}
                className={`chat-msg ${m.role} ${m.status === 'error' ? 'error' : ''}`
                  + `${m.role === 'assistant' && m.status === 'streaming' ? ' is-streaming' : ''}`}>
                {m.role === 'assistant' && runningTool && (
                  <div className="chat-dock" data-testid="chat-dock" role="status">
                    <span className="chat-live-dot" aria-hidden="true" />
                    {TOOL_SERVICE[runningTool.name] || TOOL_MACHINE[runningTool.name] || 'Local service'}
                    {' · '}
                    {toolLabel(runningTool.name, runningTool.label)}
                    {runningTool.pct != null ? ` · ${runningTool.pct}%` : ''}
                  </div>
                )}
                {m.role === 'assistant' && toolCount > 0 && (
                  <div className="chat-tools" data-testid="chat-tools">
                    {m.tools.map((tj) => (
                      <div key={tj.call_id} className={`chat-tool ${tj.status}`}>
                        <span className="chat-tool-icon" aria-hidden="true">
                          <Icon name={tj.status === 'error' ? 'alert'
                            : tj.status === 'done' ? 'check' : 'settings'} size={15} />
                        </span>
                        <span className="chat-tool-name">{toolLabel(tj.name, tj.label)}</span>
                        <span className="chat-tool-state">
                          {tj.status === 'running'
                            ? [tj.pct != null ? `${tj.pct}%` : null, tj.label].filter(Boolean).join(' · ') || 'working…'
                            : tj.status === 'done' ? 'done' : 'failed'}
                        </span>
                        <span className="chat-tool-machine">{TOOL_MACHINE[tj.name] || tj.name}</span>
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
                        <AssetMedia asset={a} onOpen={() => setLightbox(a)} />
                        <span className="chat-asset-meta">
                          <span>
                            {a.name || 'asset'}
                            {a.width && a.height ? ` · ${a.width}×${a.height}` : ''}
                          </span>
                          {a.kind && <span className="chat-asset-kind">{a.kind}</span>}
                        </span>
                        <span className="chat-asset-actions">
                          {(!a.kind || a.kind === 'image') && (
                            <button type="button" onClick={() => setLightbox(a)}>
                              <Icon name="eye" size={13} /> View
                            </button>
                          )}
                          <button type="button"
                            onClick={() => { saveAsset(a.id, a.name).catch(() => {}) }}>
                            <Icon name="download" size={13} /> Download
                          </button>
                          <button type="button" onClick={() => copyText(a.id)}>
                            <Icon name="copy" size={13} /> Copy id
                          </button>
                          {onOpenAdvanced && (
                            <button type="button" title="Open the Advanced studio to composite this"
                              onClick={() => onOpenAdvanced('/design-studio')}>
                              <Icon name="palette" size={13} /> Open in studio
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
                    {celebrateId === m.id && (
                      <span className="chat-comet" aria-hidden="true" data-testid="chat-comet" />
                    )}
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
                      onClick={() => {
                        if (noteFor === m.id) { rate(m, 'down', noteText); setNoteFor('') }
                        else { setNoteFor(m.id); setNoteText('') }
                      }}>
                      {ratings[m.id] === 'down' ? 'Gap recorded'
                        : noteFor === m.id ? 'Send note' : 'Wrong'}
                    </button>
                  </div>
                )}
                {m.role === 'assistant' && noteFor === m.id && !ratings[m.id] && (
                  <div className="chat-msg-tools" style={{ gap: 8 }}>
                    <input
                      value={noteText}
                      onChange={(e) => setNoteText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') { rate(m, 'down', noteText); setNoteFor('') }
                      }}
                      placeholder="What was wrong? (optional — one line)"
                      aria-label="What was wrong"
                      style={{ flex: '1 1 260px', padding: '6px 10px', borderRadius: 8 }}
                    />
                    <button type="button" className="chat-msg-copy"
                      onClick={() => { rate(m, 'down', noteText); setNoteFor('') }}>
                      Send note
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
                  <Icon name={m === 'image' ? 'image' : 'film'} size={14} /> {m === 'image' ? 'Image' : 'Video'}
                </button>
              ))}
            </div>
            <button type="button"
              className={`chat-options-toggle ${optionsOpen ? 'is-open' : ''}`}
              aria-expanded={optionsOpen} aria-controls="chat-options"
              onClick={() => setOptionsOpen((v) => !v)} data-testid="chat-options-toggle">
              <Icon name="settings" size={14} /> Options
              <span className="chat-options-sum">
                Mode: {mode} · {style} · effort: {thinking}
              </span>
            </button>
            <span className="chat-controls-spacer" />
            {/* Pick an asset that ALREADY exists in the studio library.
                The paperclip uploads a new file and needs a native file dialog,
                which no browser-automation controller can drive; brand assets
                (logo, plates, previous renders) are already catalogued, so the
                honest path is to select them by id. Selecting one attaches it to
                the next turn exactly like an upload does, and the tools take the
                asset id (apply_label: plate_asset_id / logo_asset_id). */}
            <button type="button" className="chat-icon-btn" title="Use a studio asset"
              onClick={() => { setAssetPickerOpen((v) => !v); loadStudioAssets() }}
              data-testid="chat-asset-picker-toggle" aria-label="Use a studio asset"
              aria-expanded={assetPickerOpen} aria-busy={studioAssetsState === 'loading'}>
              {studioAssetsState === 'loading' && assetPickerOpen
                ? <span className="chat-spinner" aria-hidden="true" />
                : <Icon name="image" size={17} />}
            </button>
            <button type="button" className="chat-icon-btn" title="Attach a file"
              onClick={() => fileRef.current?.click()} disabled={uploading}
              data-testid="chat-attach" aria-label="Attach a file">
              {uploading
                ? <span className="chat-spinner" aria-hidden="true" />
                : <Icon name="upload" size={17} />}
            </button>
            <button type="button"
              className={`chat-icon-btn ${recording ? 'is-live' : ''}`}
              title={recording
                ? 'Stop dictation'
                : 'Dictate a message (records locally, transcribes with whisper.cpp)'}
              onClick={() => (recording ? stopRecording() : startRecording())}
              aria-pressed={recording} data-testid="chat-dictate"
              aria-label={recording ? 'Stop dictation' : 'Dictate a message'}
              disabled={transcribing}>
              {transcribing
                ? <span className="chat-spinner" aria-hidden="true" />
                : recording
                  ? <span className="chat-live-dot" aria-hidden="true" />
                  : <Icon name="mic" size={17} />}
            </button>
            <button type="button"
              className={`chat-icon-btn ${speakReplies ? 'is-live' : ''}`}
              title={speakReplies
                ? 'Spoken replies are on — turn off'
                : 'Speak replies aloud (local voice engine)'}
              onClick={toggleSpeakReplies}
              aria-pressed={speakReplies} data-testid="chat-speak-replies"
              aria-label="Speak replies aloud">
              <Icon name="volume" size={17} />
            </button>
            {LIVE_VOICE_ENABLED && (
              <button type="button"
                className={`chat-icon-btn ${conversation ? 'is-live' : ''}`}
                title={conversation ? 'End the live conversation' : 'Start a live conversation'}
                onClick={() => (conversation ? stopConversation() : startConversation())}
                aria-pressed={conversation} data-testid="chat-conversation"
                aria-label={conversation ? 'End the live conversation' : 'Start a live conversation'}>
                {conversation
                  ? (voiceState === 'speaking' ? <Icon name="volume" size={17} />
                    : voiceState === 'thinking' ? <span className="chat-spinner" aria-hidden="true" />
                      : <span className="chat-live-dot" aria-hidden="true" />)
                  : <Icon name="mic" size={17} />}
              </button>
            )}
            <input aria-label="Attach a file" ref={fileRef} type="file" hidden
              accept="image/*,video/*,application/pdf,text/plain,text/csv"
              onChange={(e) => uploadFile(e.target.files && e.target.files[0])}
              data-testid="chat-file" />
          </div>
          {optionsOpen && (
            <div className="chat-options" id="chat-options">
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
            </div>
          )}
          {voiceNote && (
            <div className="chat-note" role="status" data-testid="chat-voice-note">
              <Icon name="alert" size={15} />
              <span className="chat-note-text">{voiceNote}</span>
              <button type="button" className="chat-note-close" aria-label="Dismiss"
                onClick={() => setVoiceNote('')}><Icon name="x" size={14} /></button>
            </div>
          )}
          {assetPickerOpen && (
            <div className="chat-asset-picker" data-testid="chat-asset-picker" role="dialog"
              aria-label="Select a studio asset">
              <div className="chat-asset-picker-head">
                <strong>Studio assets</strong>
                <span className="chat-asset-picker-note">
                  {studioAssetsState === 'loading' ? 'loading…'
                    : studioAssetsState === 'empty' ? 'none yet'
                      : studioAssetsState === 'error' ? 'unavailable'
                        : `${studioAssets.length} available`}
                </span>
                <button type="button" className="chat-icon-btn" aria-label="Close asset picker"
                  data-testid="chat-asset-picker-close"
                  onClick={() => setAssetPickerOpen(false)}><Icon name="x" size={14} /></button>
              </div>
              <div className="chat-asset-picker-list">
                {studioAssetsState === 'loading' && (
                  <div className="chat-asset-picker-status" data-testid="chat-asset-picker-loading"
                    role="status">
                    <span className="chat-spinner" aria-hidden="true" /> Loading studio assets…
                  </div>
                )}
                {studioAssetsState === 'error' && (
                  <div className="chat-asset-picker-status" data-testid="chat-asset-picker-error"
                    role="status">
                    The asset library could not be read.
                  </div>
                )}
                {studioAssetsState !== 'loading' && studioAssetsState !== 'error'
                  && studioAssets.length === 0 && (
                  <div className="chat-asset-picker-status" data-testid="chat-asset-picker-empty"
                    role="status">
                    No studio assets yet.
                  </div>
                )}
                {studioAssets.map((a) => (
                  <button key={a.id} type="button" className="chat-asset-option"
                    data-testid="chat-asset-option" data-asset-id={a.id}
                    data-asset-type={a.asset_type || ''}
                    title={`${a.name || a.id} (${a.asset_type || 'asset'})`}
                    onClick={() => attachExistingAsset(a)}>
                    <img src={`/api/design-studio/assets/${a.id}/file`} alt="" loading="lazy" />
                    <span className="chat-asset-option-name">{a.name || a.id}</span>
                    <span className="chat-asset-option-kind">{a.asset_type || 'asset'}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
          {attachments.length > 0 && (
            <div className="chat-attachments" data-testid="chat-attachments">
              {attachments.map((a) => (
                <span key={a.id} className="chat-attachment">
                  <Icon name="file" size={13} />
                  {a.name}
                  <button type="button" aria-label={`Remove ${a.name}`}
                    onClick={() => setAttachments((prev) => prev.filter((x) => x.id !== a.id))}>
                    <Icon name="x" size={13} />
                  </button>
                </span>
              ))}
            </div>
          )}
          {uploadNote && (
            <div className="chat-note" role="status">
              <Icon name="alert" size={15} />
              <span className="chat-note-text">{uploadNote}</span>
              <button type="button" className="chat-note-close" aria-label="Dismiss"
                onClick={() => setUploadNote('')}><Icon name="x" size={14} /></button>
            </div>
          )}
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
                <span className="chat-live-dot" aria-hidden="true" /> {recordSeconds}s — stop
              </button>
            ) : (
              <button type="button" className="btn btn-sm" onClick={startRecording}
                disabled={transcribing || !!voiceDisabled} data-testid="chat-voice"
                title={voiceDisabled
                  ? `Dictation unavailable: ${voiceStatus.detail || 'whisper not found'}`
                  : 'Dictate: record, transcribe, then answer (local whisper.cpp)'}
                aria-label="Dictate a message">
                {transcribing
                  ? <><span className="chat-spinner" aria-hidden="true" /> Transcribing…</>
                  : <><Icon name="mic" size={14} /> Dictate</>}
              </button>
            )}
            <button type="button" className="btn btn-primary btn-sm" onClick={() => send()}
              disabled={!input.trim()} data-testid="chat-send" aria-label="Send">
              <Icon name="send" size={14} /> Send
            </button>
          </div>
          <div className="chat-hint">
            Enter sends · Shift+Enter newline · Stop saves the partial as partial
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
            <AssetImage assetId={lightbox.id} alt={lightbox.name || 'asset'} />
            <div className="chat-lightbox-bar">
              <span>{lightbox.name || 'asset'}</span>
              <button type="button"
                onClick={() => { saveAsset(lightbox.id, lightbox.name).catch(() => {}) }}>
                <Icon name="download" size={13} /> Download
              </button>
              <button type="button" onClick={() => copyText(lightbox.id)}>
                <Icon name="copy" size={13} /> Copy id
              </button>
              <button type="button" onClick={() => setLightbox(null)}>
                <Icon name="x" size={13} /> Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
