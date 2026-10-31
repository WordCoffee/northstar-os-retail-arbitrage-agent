import CelestialBackdrop from '../../shell/CelestialBackdrop.jsx'
import CommandDeck from '../../galactic/CommandDeck.jsx'
import '../../styles/celestial.css'

// Phase 2 visual layer: the deck keeps its own page in Simple and Advanced
// modes. The celestial backdrop is CSS-only (the WebGL GalacticBackdrop remains
// the shell's atmosphere), so this surface does not compete with FLUX 3 for GPU.
export default function GalacticDeck() {
  return (
    <div className="gx-page">
      <CelestialBackdrop />
      <div className="gx-page-content">
        <CommandDeck />
      </div>
    </div>
  )
}
