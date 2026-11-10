// SceneHost is the shell's single mount point: it turns "where am I" into
// "which scene", and delegates the canvas to SceneSurface.

import { describe, it, expect } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import SceneHost from './SceneHost.jsx'
import { DEFAULT_SCENE_SERVICE } from '../scenes/sceneRegistry.js'

const LIVE = { webgl2: true, reducedMotion: false }
const NO_WEBGL = { webgl2: false, reducedMotion: false }

describe('SceneHost', () => {
  it('prefers the active tab id over the path', () => {
    const html = renderToStaticMarkup(
      <SceneHost serviceId="adpilot" pathname="/listings" environment={LIVE} />,
    )
    expect(html).toContain('data-scene-id="adpilot"')
  })

  it('derives the scene from the path when there is no tab', () => {
    const html = renderToStaticMarkup(
      <SceneHost pathname="/keyword-tracker" environment={LIVE} />,
    )
    expect(html).toContain('data-scene-id="keyword-tracker"')
  })

  it('renders the home scene for a non-workspace route', () => {
    const html = renderToStaticMarkup(<SceneHost pathname="/home" environment={LIVE} />)
    expect(html).toContain(`data-scene-id="${DEFAULT_SCENE_SERVICE}"`)
  })

  it('mounts exactly one canvas for the whole shell', () => {
    const html = renderToStaticMarkup(
      <SceneHost serviceId="listings" pathname="/listings" environment={LIVE} />,
    )
    expect(html.match(/<canvas/g)).toHaveLength(1)
  })

  it('falls back to the poster without WebGL2', () => {
    const html = renderToStaticMarkup(
      <SceneHost serviceId="listings" pathname="/listings" environment={NO_WEBGL} />,
    )
    expect(html).toContain('data-scene-mode="static"')
    expect(html).not.toContain('<canvas')
  })
})
