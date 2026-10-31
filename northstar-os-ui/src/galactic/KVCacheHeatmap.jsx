import { formatContext, heatmapCells } from '../lib/galacticState.js'

// KV-cache / context heatmap. A known ratio is a filled row; a lane with no
// instrumentation is hatched and says "unknown" rather than inventing 0%.
export default function KVCacheHeatmap({ kv = [] }) {
  const rows = heatmapCells(kv)
  return (
    <div className="gx-heatmap">
      <div className="gx-heatmap-head">
        <span>KV cache · context window</span>
        <span className="gx-legend">
          <i className="gx-swatch gx-swatch--used" /> used
          <i className="gx-swatch gx-swatch--free" /> free
          <i className="gx-swatch gx-swatch--unknown" /> unknown
        </span>
      </div>
      {rows.length === 0 && <p className="gx-empty">No KV lanes reported.</p>}
      {rows.map((row) => (
        <div className="gx-heat-row" key={row.id} data-known={row.known ? 'true' : 'false'}>
          <div className="gx-heat-label">
            <strong>{row.label}</strong>
            <span>
              {row.known
                ? `${formatContext(row.context_used)} / ${formatContext(row.context_total)}`
                : row.context_total
                  ? `${formatContext(row.context_total)} capacity · usage not instrumented`
                  : 'usage not instrumented'}
              {row.kv_cache ? ` · ${row.kv_cache}` : ''}
            </span>
          </div>
          <div
            className="gx-heat-cells"
            role="img"
            aria-label={`${row.label}: ${row.known ? `${Math.round(row.ratio * 100)} percent of context used` : 'context usage unavailable'}`}
          >
            {row.cells.map((cell) => (
              <i
                key={cell.i}
                className={`gx-cell ${cell.active ? 'is-active' : ''} ${cell.unknown ? 'is-unknown' : ''} ${cell.partial ? 'is-partial' : ''}`}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
