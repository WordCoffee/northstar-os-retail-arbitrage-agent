import { PageLayout, DataTable, DataNotice } from '../../components/Shared.jsx'
import RoomTabs from '../../components/RoomTabs.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import { useLocation } from 'react-router-dom'

const TABS = [
  { id: 'sessions', label: 'Sessions', count: 3 },
  { id: 'decisions', label: 'Decision Flow' },
  { id: 'reasoning', label: 'Reasoning Checkpoints' },
  { id: 'control', label: 'Control' },
]

export default function MasterBrain() {
  const { toast } = useToast()
  const location = useLocation()

  const requested = new URLSearchParams(location.search).get('view') || ''
  const view = TABS.some(t => t.id === requested) ? requested : 'sessions'

  return (
    <PageLayout
      title="Master Brain"
      subtitle="Orchestration visibility — active sessions, decision flow, reasoning checkpoints, and control surfaces."
      actions={<>
        <button className="btn btn-sm" onClick={() => toast('Sessions view — active runs and their engines.', 'info')}>View Sessions</button>
        <button className="btn btn-sm btn-ghost" onClick={() => toast('Decision Log — full reasoning trail per decision.', 'info')}>Decision Log</button>
      </>}
    >
      <DataNotice tone="internal" title="Research assistance only">
        Master Brain does NOT authorize purchases, make pricing decisions, or contact providers without explicit operator approval. Confidence values are internal estimates, not verified fact.
      </DataNotice>

      <RoomTabs tabs={TABS} base="/master-brain" />

      {view === 'sessions' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Active Sessions</h3>
              <span className="pill pill-forest">3 running</span>
            </div>
            <DataTable columns={[
              { key: 'session', label: 'Session' },
              { key: 'engine', label: 'Engine' },
              { key: 'focus', label: 'Focus' },
              { key: 'started', label: 'Started' },
              { key: 'state', label: 'State' },
            ]} rows={[
              { session: 'S-001', engine: 'Ling 3.0 Flash', focus: 'Buy box risk — Set A', started: '10:04', state: 'Running' },
              { session: 'S-002', engine: 'Northstar Inline', focus: 'Margin hypothesis scan', started: '09:41', state: 'Queued' },
              { session: 'S-003', engine: 'Ling 3.0 Flash', focus: 'Listing copy quality', started: '08:12', state: 'Review' },
            ]} />
          </div>
        </div>
      )}

      {view === 'decisions' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Decision Flow — Recent</h3>
              <span className="pill pill-muted">47 today</span>
            </div>
            <DataTable columns={[
              { key: 'input', label: 'Input' },
              { key: 'decision', label: 'Decision' },
              { key: 'confidence', label: 'Confidence' },
              { key: 'model', label: 'Model' },
              { key: 'state', label: 'State' },
            ]} rows={[
              { input: 'SourceScout B08L5VJQ7T', decision: 'Researching', confidence: '42%', model: 'Internal v2', state: 'In Progress' },
              { input: 'GG-001 Opportunity', decision: 'Hold for verification', confidence: '55%', model: 'Internal v2', state: 'Waiting' },
              { input: 'Portfolio Set B analysis', decision: 'Monitor closely', confidence: '68%', model: 'Internal v2', state: 'Active' },
              { input: 'Keyword gap analysis', decision: 'Recommend listing update', confidence: '74%', model: 'Internal v2', state: 'Complete' },
            ]} />
          </div>
        </div>
      )}

      {view === 'reasoning' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Reasoning Checkpoints</h3>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Cost basis validation — BLOCKED until invoice verified</div>
                <span className="pill pill-error">Block</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Pack identity match — AWAITING operator input</div>
                <span className="pill pill-warn">Wait</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Market trend analysis — COMPLETE</div>
                <span className="pill pill-ok">OK</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'control' && (
        <div className="subview">
          <div className="card">
            <div className="card-head">
              <h3 className="card-title">Control Surfaces</h3>
            </div>
            <div className="stack" style={{ gap: 8 }}>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Purchase authorization</div>
                <span className="pill pill-error">Locked</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Pricing decisions</div>
                <span className="pill pill-error">Locked</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Provider contact</div>
                <span className="pill pill-error">Locked</span>
              </div>
              <div className="list-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0' }}>
                <div style={{ fontSize: 13 }}>Research runs</div>
                <span className="pill pill-forest">Available</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </PageLayout>
  )
}