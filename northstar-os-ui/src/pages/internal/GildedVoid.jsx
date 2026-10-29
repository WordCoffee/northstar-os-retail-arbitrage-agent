// The Gilded Void — the live stage for the Baroque Hyperrealism theme
// (reports/baroque_hyperrealism_spec_20261029_153346.md). Renders all five
// manifest components with the spec's interactive dynamics: the cursor is
// the light source, CTAs ripple on click, and the modal draws its curtain.

import { useCallback, useState } from 'react'
import BaroqueBackdrop, { BaroqueFilters } from '../../components/baroque/BaroqueBackdrop.jsx'
import ControlFrame from '../../components/baroque/ControlFrame.jsx'
import StatusBanner from '../../components/baroque/StatusBanner.jsx'
import ActionTrigger from '../../components/baroque/ActionTrigger.jsx'
import NotificationModal from '../../components/baroque/NotificationModal.jsx'
import { useBaroqueLight, useBaroqueModal } from '../../components/baroque/baroque.js'

export default function GildedVoid() {
  const { open, closing, openModal, closeModal } = useBaroqueModal()
  const [light, setLight] = useState({ x: null, y: null })
  const onMove = useCallback((x, y) => setLight({ x, y }), [])
  const stageRef = useBaroqueLight(onMove)
  const [pulses, setPulses] = useState(0)

  return (
    <div className="baroque-stage" ref={stageRef}>
      <BaroqueFilters />
      <BaroqueBackdrop dimmed={open} />

      <header className="baroque-header">
        <div className="baroque-eyebrow">Northstar OS · Visual System</div>
        <h1 className="baroque-title">The Gilded Void</h1>
        <p className="baroque-lede">
          Hyperrealistic Baroque stage — chiaroscuro marble, gold leaf, velvet.
          Move the cursor: it is the light source.
        </p>
      </header>

      <ControlFrame eyebrow="Component 1 · Gilded Control Frame" title="The Stage">
        <StatusBanner tone="ok" label="System status">
          All systems nominal — light source tracking active
        </StatusBanner>

        <div className="baroque-stage-row">
          <ActionTrigger label="Raise the curtain" onClick={openModal} />
          <ActionTrigger
            label="Log a stage pulse"
            variant="ghost"
            onClick={() => setPulses((p) => p + 1)}
          />
        </div>

        <div className="baroque-readout">
          <span>
            Light source: {light.x == null ? 'awaiting cursor' : `${light.x.toFixed(1)}% , ${light.y.toFixed(1)}%`}
          </span>
          <span>Stage pulses: {pulses}</span>
        </div>
      </ControlFrame>

      <NotificationModal open={open} closing={closing} onClose={closeModal} title="Theatrical Notification">
        <p>
          The curtain has been drawn back. This marble panel floats above the
          stage on a deep drop shadow, trimmed in gold.
        </p>
        <div className="baroque-modal-actions">
          <ActionTrigger label="Close the curtain" onClick={closeModal} />
        </div>
      </NotificationModal>
    </div>
  )
}
