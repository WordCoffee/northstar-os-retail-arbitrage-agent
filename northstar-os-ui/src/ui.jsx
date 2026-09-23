import Icon from './components/Icon.jsx'

export function PageHead({ title, sub, badges = [], right }) {
  return (
    <div className="page-head">
      <div className="title-block">
        <h1 className="text-glow">{title}</h1>
        <p>{sub}</p>
        <div className="meta-line">
          {badges.map((b) => (
            <span key={b.label} className={`badge badge-${b.tone}`}>{b.label}</span>
          ))}
        </div>
      </div>
      {right}
    </div>
  )
}

export function Card({ title, icon, children, className = '', style }) {
  return (
    <div className={`card ${className}`} style={style}>
      {title && (
        <h3>
          {icon && <Icon name={icon} size={14} />}
          {title}
        </h3>
      )}
      {children}
    </div>
  )
}

export function Metric({ k, v, d, tone }) {
  return (
    <div className="metric-tile">
      <div className="k">{k}</div>
      <div className={`v ${tone || ''}`}>{v}</div>
      {d && <div className="d">{d}</div>}
    </div>
  )
}

export function Gate({ name, desc, state = 'off', toast }) {
  const tone = state === 'on' ? 'on' : 'off'
  return (
    <div className="gate-row">
      <div>
        <div className="gate-name">{name}</div>
        <div className="gate-desc">{desc}</div>
      </div>
      <button
        className={`status-pill ${state === 'warn' ? 'warn' : tone}`}
        onClick={() => toast(`${name}: ${state === 'on' ? 'live — requires operator approval' : 'closed'}`, state === 'on' ? 'ok' : 'err')}
        aria-pressed={state === 'on'}
      >
        <span className={`pulse-dot ${state !== 'on' ? '' : ''}`} style={{ opacity: state === 'on' ? 1 : 0.25, background: state === 'on' ? 'var(--lime)' : 'var(--text-low)' }} />
        {state === 'on' ? 'LIVE' : state === 'warn' ? 'REVIEW' : 'Authorization required'}
      </button>
    </div>
  )
}

export function SectionTitle({ text }) {
  return <div className="sidebar-section" style={{ margin: '10px 0' }}>{text}</div>
}