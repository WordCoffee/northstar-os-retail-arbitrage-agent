import { layoutTopology, topologyLinks } from '../lib/galacticState.js'

// Stellar Node Topology: the orchestrator at the centre, workers on a stable
// ring. SVG is used instead of canvas so every node is keyboard-focusable and
// has an accessible name; the animation is a CSS halo, not a render loop.
export default function NodeTopology({ nodes = [], links = [], selected = '', onSelect, pulse = 0 }) {
  const laid = layoutTopology(nodes)
  const edges = topologyLinks(nodes, links)
  const byId = new Map(laid.map((n) => [n.id, n]))

  return (
    <div className="gx-topology-wrap" data-pulse={pulse}>
      <svg
        className="gx-topology"
        viewBox="0 0 1000 600"
        role="img"
        aria-label="Agent node topology: orchestrator at centre, compute, memory, media, browser and worker nodes on a ring"
      >
        <defs>
          <radialGradient id="gx-core" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(155,123,255,0.55)" />
            <stop offset="100%" stopColor="rgba(155,123,255,0)" />
          </radialGradient>
          <filter id="gx-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="7" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        <circle cx="500" cy="300" r="230" fill="url(#gx-core)" opacity="0.35" />
        {edges.map((edge) => (
          <line
            key={`${edge.from}-${edge.to}`}
            className="gx-link"
            x1={edge.x1} y1={edge.y1} x2={edge.x2} y2={edge.y2}
          />
        ))}
        {laid.map((node) => {
          const isSelected = node.id === selected
          return (
            <g
              key={node.id}
              className={`gx-node ${isSelected ? 'is-selected' : ''} ${node.centre ? 'is-centre' : ''}`}
              data-tone={node.tone}
              transform={`translate(${node.x} ${node.y})`}
              role="button"
              tabIndex={0}
              aria-label={`${node.label} — ${node.role || 'node'}${node.status ? `, ${node.status}` : ''}`}
              aria-pressed={isSelected}
              onClick={() => onSelect?.(node.id)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  onSelect?.(node.id)
                }
              }}
            >
              <circle className="gx-node-halo" r={node.r + 10} />
              <circle className="gx-node-disc" r={node.r} filter={node.centre ? 'url(#gx-glow)' : undefined} />
              <text className="gx-node-label" y={node.r + 24} textAnchor="middle">
                {node.label}
              </text>
              <text className="gx-node-meta" y={node.r + 42} textAnchor="middle">
                {node.model || node.role || ''}
              </text>
              {node.status && (
                <text className="gx-node-status" y={-node.r - 12} textAnchor="middle">
                  {node.status}
                </text>
              )}
            </g>
          )
        })}
        {byId.size === 0 && (
          <text x="500" y="300" textAnchor="middle" className="gx-empty">
            No nodes reported
          </text>
        )}
      </svg>
    </div>
  )
}
