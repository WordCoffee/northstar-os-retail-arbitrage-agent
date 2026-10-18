// ═══════════════════════════════════════════════════════════════════════════
// IMMERSIVE PLAN GRAPH (V3 S5 · deep-visual pass)
//
// The reconstructed agent plan as an animated node-link constellation over a
// deep-space background — woven into the cosmic shell. Honest shape: a linear
// chain (the bounded tool loop is sequential), drawn beautifully.
//
//   prompt ──▶ step 0 ──▶ step 1 ──▶ … ──▶ answer
//
// Nodes glow (forest = input, cobalt spark = AI step, pine = answer). Edges
// draw themselves. The whole chain reveals sequentially, one node at a time,
// echoing how the turn loop actually ran. Purely presentational; nothing here
// invents edges or dependencies.
//
// Dark-glass panel over the cosmic background. Respects prefers-reduced-motion
// (falls back to a static chain).
// ════════════════════════════════════════════════════════════════════════════

import { useCallback, useEffect, useRef, useState } from 'react'

const NODE_R = 24              // node circle radius
const GAP = 112                // vertical gap between nodes (px)
const TOP = 96                 // title offset
const BOTTOM = 44

function kindColor(kind) {
  return { prompt: 'forest', tool: 'spark', answer: 'pine' }[kind] || 'pine'
}

function kindAccent(kind) {
  return { prompt: 'var(--forest)', tool: 'var(--spark)', answer: 'var(--pine)' }[kind] || 'var(--pine)'
}

function statusFill(status) {
  return {
    done: 'var(--status-ok)',
    error: 'var(--status-error)',
    cancelled: 'var(--status-unknown)',
    running: 'var(--spark)',
    queued: 'var(--ink-faint)',
  }[status] || 'var(--ink-faint)'
}

export default function ImmersivePlanGraph({ plan, className }) {
  const wrapRef = useRef(null)
  const [size, setSize] = useState({ w: 0, h: 0 })
  const [revealed, setRevealed] = useState(false)
  const roRef = useRef(null)

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      const cr = entries[0].contentRect
      setSize({ w: Math.max(1, Math.floor(cr.width)), h: Math.max(1, Math.floor(cr.height)) })
    })
    ro.observe(el)
    roRef.current = ro
    setSize({ w: Math.max(1, Math.floor(el.clientWidth)), h: Math.max(1, Math.floor(el.clientHeight)) })
    const t = setTimeout(() => setRevealed(true), 120)
    return () => { clearTimeout(t); ro.disconnect() }
  }, [])

  if (!plan || !plan.nodes || !plan.nodes.length) {
    return (
      <div className={`ipg-panel ${className || ''}`} ref={wrapRef}>
        <div className="ipg-bg" />
        <div className="ipg-empty">
          <div className="ipg-empty-dot" aria-hidden="true" />
          <div className="ipg-empty-title">No plan yet</div>
          <div className="ipg-empty-sub">Send a message and the Master Brain will trace its steps here.</div>
        </div>
      </div>
    )
  }

  const nodes = plan.nodes
  const edges = plan.edges || []
  const edgeBySrc = new Map()
  edges.forEach((e) => edgeBySrc.set(e[0], e[1]))

  const { w, h } = size
  const padX = 36
  const cx = w / 2
  const n = nodes.length
  const avail = Math.max(1, h - TOP - BOTTOM)
  const gap = Math.min(GAP, Math.max(56, avail / Math.max(1, n - 1)))

  const pos = new Map()
  nodes.forEach((node, i) => {
    pos.set(node.id, { x: cx, y: TOP + i * gap })
  })

  const reduced =
    typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

  return (
    <div className={`ipg-panel ${className || ''}`} ref={wrapRef}
      data-testid="chat-workbench-plan"
      style={{ minHeight: Math.max(260, n * gap + TOP + BOTTOM) }}>
      <div className="ipg-bg" />
      <div className="ipg-stars" aria-hidden="true" />
      <svg
        className="ipg-svg"
        width="100%"
        height="100%"
        style={{ display: 'block' }}
        aria-label="Agent plan — reconstructed tool chain"
      >
        <defs>
          <filter id="ipg-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
          <linearGradient id="ipg-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(255,255,255,0.14)" />
            <stop offset="100%" stopColor="rgba(255,255,255,0.02)" />
          </linearGradient>
        </defs>

        {/* ── edges (drawn behind nodes) ── */}
        <g className="ipg-edges">
          {nodes.map((node, i) => {
            const dst = edgeBySrc.get(node.id)
            if (!dst) return null
            const a = pos.get(node.id)
            const b = pos.get(dst)
            if (!a || !b) return null
            const len = b.y - a.y - NODE_R * 2
            return (
              <line
                key={`e-${i}`}
                x1={a.x}
                y1={a.y + NODE_R}
                x2={b.x}
                y2={b.y - NODE_R}
                stroke="var(--divider-strong)"
                strokeWidth="2"
                strokeLinecap="round"
                className={`ipg-edge ${reduced ? 'ipg-edge-static' : 'ipg-edge-draw'}`}
                style={{
                  strokeDasharray: len,
                  strokeDashoffset: revealed ? 0 : len,
                  transition: reduced ? 'none' : `stroke-dashoffset 700ms cubic-bezier(0.4, 0, 0.2, 1) ${i * 180}ms`,
                  opacity: revealed ? 1 : 0,
                }}
              />
            )
          })}
        </g>

        {/* ── nodes ── */}
        <g className="ipg-nodes">
          {nodes.map((node, i) => {
            const p = pos.get(node.id)
            const color = kindAccent(node.kind)
            const filled = statusFill(node.status)
            const active = node.kind === 'tool' && (node.status === 'running' || node.status === 'queued')
            const done = node.status === 'done'
            const delay = revealed ? i * 150 : 0
            const label = node.label || node.name || (node.kind === 'answer' ? 'Answer' : 'Prompt')
            const meta =
              node.kind === 'tool' && node.elapsed_ms != null
                ? `${node.elapsed_ms} ms`
                : node.kind === 'tool'
                ? node.status
                : ''
            return (
              <g key={node.id} transform={`translate(${p.x - NODE_R},${p.y - NODE_R})`}>
                <circle
                  cx={NODE_R}
                  cy={NODE_R}
                  r={NODE_R}
                  className={`ipg-node ${node.kind} ${active ? 'ipg-node-active' : ''} ${done ? 'ipg-node-done' : ''}`}
                  style={{
                    fill: 'rgba(26, 46, 26, 0.62)',
                    stroke: color,
                    strokeWidth: active ? 3 : done ? 2.5 : 1.5,
                    filter: active || done ? 'url(#ipg-glow)' : 'none',
                    opacity: revealed ? 1 : 0,
                    transform: revealed ? 'scale(1)' : 'scale(0.85)',
                    transition: reduced
                      ? 'none'
                      : `opacity 450ms cubic-bezier(0.4, 0, 0.2, 1) ${delay}ms, transform 450ms cubic-bezier(0.4, 0, 0.2, 1) ${delay}ms, stroke 300ms ${delay}ms`,
                  }}
                />
                {/* status dot */}
                <circle
                  cx={NODE_R + 14}
                  cy={NODE_R - 14}
                  r={7}
                  fill={filled}
                  stroke="var(--surface)"
                  strokeWidth="1.5"
                  className="ipg-status-dot"
                  style={{ opacity: revealed ? 1 : 0, transform: revealed ? 'scale(1)' : 'scale(0.6)', transition: reduced ? 'none' : `transform 350ms cubic-bezier(0.4,0,0.2,1) ${delay + 60}ms, opacity 300ms ${delay + 60}ms` }}
                />
                {/* glow ring for active tool step */}
                {active && (
                  <circle
                    cx={NODE_R}
                    cy={NODE_R}
                    r={NODE_R + 10}
                    fill="none"
                    stroke="var(--spark)"
                    strokeWidth="1.5"
                    opacity={reduced ? 0 : 0.55}
                    className="ipg-node-pulse"
                    style={{
                      opacity: 0.55,
                      animation: reduced ? 'none' : `ipg-pulse 2.2s ease-in-out infinite ${delay}ms`,
                    }}
                  />
                )}
                {/* kind + name */}
                <text
                  x={NODE_R + 10}
                  y={NODE_R - 6}
                  fill={color}
                  fontFamily="var(--font-ui)"
                  fontSize="10"
                  fontWeight="700"
                  letterSpacing="0.06em"
                  textTransform="uppercase"
                  style={{ opacity: revealed ? 1 : 0, transition: reduced ? 'none' : `opacity 350ms ${delay + 40}ms` }}
                >
                  {node.kind === 'tool' && node.name ? node.name : kindColor(node.kind)}
                </text>
                {/* label */}
                <text
                  x={NODE_R + 10}
                  y={NODE_R + 10}
                  fill="var(--ink)"
                  fontFamily="var(--font-ui)"
                  fontSize="11.5"
                  fontWeight="600"
                  style={{ opacity: revealed ? 1 : 0, transition: reduced ? 'none' : `opacity 350ms ${delay + 80}ms` }}
                  dominantBaseline="middle"
                >
                  {label.length > 42 ? `${label.slice(0, 40)}…` : label}
                </text>
                {/* meta (ms / status) */}
                {meta && (
                  <text
                    x={NODE_R + 10}
                    y={NODE_R + 24}
                    fill="var(--ink-soft)"
                    fontFamily="var(--font-mono)"
                    fontSize="9"
                    style={{ opacity: revealed ? 1 : 0, transition: reduced ? 'none' : `opacity 350ms ${delay + 120}ms` }}
                    dominantBaseline="middle"
                  >
                    {meta}
                  </text>
                )}
              </g>
            )
          })}
        </g>
      </svg>

      <div className="ipg-foot">
        <span className="ipg-legend">
          <span className="ipg-legend-dot ipg-legend-prompt" /> Prompt
          <span className="ipg-legend-dot ipg-legend-tool" /> Step
          <span className="ipg-legend-dot ipg-legend-answer" /> Answer
        </span>
        {(plan.caveats || []).length > 0 && (
          <span className="ipg-caveat">{plan.caveats[0]}</span>
        )}
      </div>
    </div>
  )
}
