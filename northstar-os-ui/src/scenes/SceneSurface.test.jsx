// The surface is where the fallback becomes observable in the DOM. Effects do
// not run in server-rendered markup, so these assertions prove the mode is
// decided during render — not patched in afterwards by a browser-only effect.

import { describe, it, expect } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import SceneSurface from './SceneSurface.jsx'
import { sceneForService } from './sceneRegistry.js'

const LIVE = { webgl2: true, reducedMotion: false }
const NO_WEBGL = { webgl2: false, reducedMotion: false }
const REDUCED = { webgl2: true, reducedMotion: true }

function render(props) {
  return renderToStaticMarkup(<SceneSurface {...props} />)
}

describe('one canvas per surface', () => {
  it('renders exactly one canvas when WebGL2 is available', () => {
    const html = render({ serviceId: 'listings', environment: LIVE })
    expect(html.match(/<canvas/g)).toHaveLength(1)
    expect(html).toContain('data-scene-mode="live"')
    expect(html).toContain('data-scene-animated="true"')
    expect(html).toContain('data-scene-id="listings"')
    expect(html).not.toContain('<img')
  })

  it('is aria-hidden and takes no pointer events', () => {
    const html = render({ serviceId: 'listings', environment: LIVE })
    expect(html).toContain('aria-hidden="true"')
    expect(html).toContain('class="scene-bed"')
    expect(html).toContain('role="presentation"')
  })
})

describe('still-frame fallback', () => {
  it('no WebGL2 -> poster image and data-scene-mode="static"', () => {
    const html = render({ serviceId: 'golden-goose', environment: NO_WEBGL })
    expect(html).toContain('data-scene-mode="static"')
    expect(html).toContain('data-scene-animated="false"')
    expect(html).toContain('<img')
    expect(html).toContain('data-scene-poster="')
    expect(html).not.toContain('<canvas')
  })

  it('the poster is the service’s own scene, not a generic grey frame', () => {
    const html = render({ serviceId: 'adpilot', environment: NO_WEBGL })
    const scene = sceneForService('adpilot')
    expect(html).toContain(`src="${scene.poster}"`)
    expect(html).toContain(`data-scene-variant="${scene.variantId}"`)
  })
})

describe('reduced motion', () => {
  it('prefers-reduced-motion -> poster, no canvas, no animation', () => {
    const html = render({ serviceId: 'autothink', environment: REDUCED })
    expect(html).toContain('data-scene-mode="reduced"')
    expect(html).toContain('data-scene-animated="false"')
    expect(html).not.toContain('<canvas')
    expect(html).toContain('<img')
  })
})

describe('switching service', () => {
  it('re-points the bed at the new scene', () => {
    const a = render({ serviceId: 'listings', environment: LIVE })
    const b = render({ serviceId: 'profitability', environment: LIVE })
    expect(a).toContain('data-scene-id="listings"')
    expect(b).toContain('data-scene-id="profitability"')
    expect(a).not.toBe(b)
  })

  it('still renders exactly one canvas after the switch', () => {
    const html = render({ serviceId: 'profitability', environment: LIVE })
    expect(html.match(/<canvas/g)).toHaveLength(1)
  })
})
