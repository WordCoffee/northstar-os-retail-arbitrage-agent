// ═══════════════════════════════════════════════════════════════════════════
// DESIGN STUDIO — SECTION: A+ › INDEXING CLAIMS (Phase 6 item 7)
//
// Every claim about what Amazon's search "indexes" that this studio records,
// with its source id, confidence and the date the source was read. Unofficial
// claims are marked REPORTED; a claim with no registry source is UNSOURCED.
//
// Alt text and on-image text carry NO recorded ranking support here, and this
// register says so out loud. The studio will not tell a seller that alt text or
// on-image text improves search ranking.
// ═══════════════════════════════════════════════════════════════════════════

import {
  INDEXING_CLAIMS, claimConfidence, claimPulledAt, claimsSupportingRanking,
  rankingAdviceFor, SUBJECT,
} from '../../../studio/engine/indexing.js'
import Icon from '../../../components/Icon.jsx'

function tierPill(c) {
  if (c === 'VERIFIED') return 'pill-ok'
  if (c === 'REPORTED') return 'pill-muted'
  return 'pill-muted'
}

export default function IndexingRegister() {
  const ranking = claimsSupportingRanking()
  const altAdvice = rankingAdviceFor(SUBJECT.ALT_TEXT)
  const imgAdvice = rankingAdviceFor(SUBJECT.IMAGE_TEXT)

  return (
    <div className="stack" style={{ gap: 14 }} data-testid="indexing-register">
      <div className="card" style={{ padding: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon name="list" size={16} />
          <strong style={{ fontSize: 14 }}>Indexing claims register</strong>
          <span className="pill pill-muted">claims, not advice</span>
        </div>
        <div className="text-low" style={{ fontSize: 12, marginTop: 6 }}>
          Each row is a claim this studio records about Amazon search, with its source id from the spec
          registry, a confidence tier, and the date that source was read. Unofficial claims are marked
          REPORTED and are never presented as instructions.
        </div>

        <div className="alert alert-warn" style={{ marginTop: 10 }} data-testid="imagery-no-ranking">
          <div className="alert-title">Imagery is not a ranking lever here</div>
          <div className="alert-text" style={{ fontSize: 12 }}>
            <div>• {altAdvice.statement}</div>
            <div>• {imgAdvice.statement}</div>
          </div>
        </div>

        <table className="table" style={{ marginTop: 12, fontSize: 12 }}>
          <thead>
            <tr>
              <th>Surface</th><th>Subject</th><th>Claim</th><th>Source</th>
              <th>Confidence</th><th>Read</th><th>Ranking support</th>
            </tr>
          </thead>
          <tbody>
            {INDEXING_CLAIMS.map(c => {
              const conf = claimConfidence(c)
              const pulled = claimPulledAt(c) || 'no source'
              return (
                <tr key={c.id}>
                  <td>{c.surface}</td>
                  <td>{c.subject}</td>
                  <td>
                    {c.claim}
                    <div className="text-low" style={{ fontSize: 11, marginTop: 2 }}>{c.note}</div>
                  </td>
                  <td>{c.source_id || 'UNSOURCED'}</td>
                  <td><span className={`pill ${tierPill(conf)}`}>{conf}{c.official ? '' : ' (unofficial)'}</span></td>
                  <td>{pulled}</td>
                  <td>{c.supports_ranking ? 'documented' : 'none recorded'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>

        <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>
          What this register will never show: advice that alt text, image text, file names or EXIF data
          improve search ranking. {ranking.length} claim(s) currently cite a documented ranking effect, all
          from listing text fields.
        </div>
      </div>
    </div>
  )
}
