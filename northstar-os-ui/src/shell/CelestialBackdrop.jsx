// ═══════════════════════════════════════════════════════════════════════════
// CELESTIAL BACKDROP (blueprint §11B.2 / brief T1–T6)
//
// The Interstellar request shipped as a plain black background, so this is a
// deliberate rebuild as LAYERS rather than one shader:
//
//   1. deep blue-black vertical gradient      (.cb-sky)
//   2. THREE star layers at different depths  (.cb-stars--far/mid/near)
//      each drifting at its own speed → real parallax
//   3. faint nebula washes                    (.cb-nebula)
//   4. ONE warm accretion glow                (.cb-accretion)
//
// Why CSS instead of WebGL: the box runs one 16 GB GPU shared with ComfyUI and
// Ollama. A full-screen fragment shader competes with render jobs and can drop
// chat frames. Composited transforms on four divs cost effectively nothing and
// are deterministic to screenshot.
//
// Reduced motion: every drift is disabled and the scene renders one static
// frame — still a visible galaxy, just not moving.
// ═══════════════════════════════════════════════════════════════════════════

export default function CelestialBackdrop() {
  return (
    <div className="celestial" data-testid="celestial-backdrop" aria-hidden="true">
      <div className="cb-sky" />
      <div className="cb-nebula cb-nebula--one" />
      <div className="cb-nebula cb-nebula--two" />
      <div className="cb-galaxy" />
      <div className="cb-blackhole" />
      <div className="cb-stars cb-stars--far" />
      <div className="cb-stars cb-stars--mid" />
      <div className="cb-stars cb-stars--near" />
      <div className="cb-accretion" />
      <div className="cb-shooting cb-shooting--one" />
      <div className="cb-shooting cb-shooting--two" />
      <div className="cb-vignette" />
    </div>
  )
}
