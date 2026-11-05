// ═══════════════════════════════════════════════════════════════════════════
// DESIGN STUDIO — /design-studio
//
// One studio for every creative output an Amazon seller needs. Phase 0 merges
// the old Product Designer (now "3D Product Scene") and Creative Studio (now
// "Projects + Asset Library") into a single route with a section picker.
//
// Unbuilt sections render an honest "Not built yet" state; they never show
// fabricated records or SAMPLE DATA banners. Built sections use real local
// records (backend DB where wired, otherwise localStorage with empty seeds).
//
// HONESTY CONTRACT (this room):
//   • Every section either works for real or says exactly what is not connected.
//   • No seeded/demo rows are displayed anywhere in this room.
//   • Generation is gated behind explicit Run actions and cost previews.
// ═══════════════════════════════════════════════════════════════════════════

import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { PageLayout } from '../../components/Shared.jsx'
import Icon from '../../components/Icon.jsx'
import { useToast } from '../../components/ToastContext.jsx'
import CreativeStudio from './CreativeStudio.jsx'
import ProductDesigner from './ProductDesigner.jsx'
import ListingImages from './design-studio/ListingImages.jsx'
import APlus from './design-studio/APlus.jsx'
import Storefront from './design-studio/Storefront.jsx'
import Ads from './design-studio/Ads.jsx'
import VideoUgc from './design-studio/VideoUgc.jsx'
import Social from './design-studio/Social.jsx'
import Packaging from './design-studio/Packaging.jsx'
import Dielines from './design-studio/Dielines.jsx'
import Deliverables from './design-studio/Deliverables.jsx'
import CanvasWorkspace from './design-studio/CanvasWorkspace.jsx'
import { migrateLocalStorage, migrationDone } from '../../studio/engine/migrate.js'

// Opt-in test surface. Adding ?engine=1 to a Design Studio URL exposes the
// studio engine on window so a browser harness can exercise the CANVAS paths
// (render, fidelity pixel extraction, export pipeline) that unit tests cannot
// reach.
//
// The gate is a COMPILE-TIME constant:
//   • Vite dev server          -> import.meta.env.DEV === true
//   • test build               -> built with VITE_TEST_HOOKS=1
//   • production build         -> both fold to false, rollup eliminates the
//                                 function body (dynamic imports included), so
//                                 the hook is not in the production bundle at
//                                 all. tools/check-prod-bundle.cjs asserts it.
// The test build is a separate artifact (dist-test) that is .gitignored,
// .dockerignored and never copied into the deploy image (Dockerfile.api copies
// only /ui/dist from its own build stage).
const ENGINE_HOOK_ENABLED = import.meta.env.DEV || import.meta.env.VITE_TEST_HOOKS === '1'

async function attachEngineHook() {
  if (!ENGINE_HOOK_ENABLED) return
  try {
    if (new URLSearchParams(window.location.search).get('engine') !== '1') return
    const [compose, fidelity, disclosure, compliance, registry] = await Promise.all([
      import('../../studio/engine/compose.js'),
      import('../../studio/engine/fidelity.js'),
      import('../../studio/engine/disclosure.js'),
      import('../../studio/engine/compliance.js'),
      import('../../studio/engine/specRegistry.js'),
    ])
    window.__northstarStudioEngine = { compose, fidelity, disclosure, compliance, registry }
  } catch { /* the hook is a convenience; never let it break the page */ }
}

const SECTIONS = [
  { id: 'canvas', label: 'Canvas', icon: 'brush', note: 'The design surface: content types, layers, snapping, autosave, PNG and PDF export', built: true },
  { id: 'projects', label: 'Projects', icon: 'stack', note: 'Project board and asset library', built: true },
  { id: 'listing-images', label: 'Listing Images', icon: 'image', note: 'Main, lifestyle, infographic modules', built: true },
  { id: 'aplus', label: 'A+ / Brand Story', icon: 'list', note: 'Amazon A+ modules and Brand Story cards', built: true },
  { id: 'storefront', label: 'Storefront', icon: 'store', note: 'Amazon Storefront pages and tiles', built: true },
  { id: 'ads', label: 'Ads', icon: 'target', note: 'Sponsored Brands video, custom images, DSP display', built: true },
  { id: 'video-ugc', label: 'Video & UGC Clips', icon: 'film', note: 'Product videos, UGC-style clips and hooks', built: true },
  { id: 'social', label: 'Social', icon: 'users', note: 'Social posts, carousels and stories', built: true },
  { id: 'packaging', label: 'Packaging & Mockups', icon: 'package', note: 'Packaging dielines and mockup renders', built: true },
  { id: 'dielines', label: 'Dielines & Print', icon: 'grid', note: 'Parametric dielines: layered SVG, PDF and project ZIP export', built: true },
  { id: 'deliverables', label: 'Asset Dashboard', icon: 'folder', note: 'Every package on disk with previews, lane triggers and the proposal queue', built: true },
  { id: '3d-scene', label: '3D Product Scene', icon: 'cube', note: 'Real 3D product scene composer', built: true },
]

function SectionPicker({ active, onChange }) {
  return (
    <div className="ds-section-picker" role="group" aria-label="Design Studio sections" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
      {SECTIONS.map(s => (
        <button
          key={s.id}
          type="button"
          className={`btn btn-sm ${active === s.id ? 'btn-primary' : ''}`}
          title={s.note}
          aria-pressed={active === s.id}
          onClick={() => onChange(s.id)}
          style={{ opacity: s.built ? 1 : 0.7 }}
        >
          <span style={{ display: 'inline-flex', marginRight: 6 }}><Icon name={s.icon} size={14} /></span>
          {s.label}
          {!s.built && <span className="pill pill-muted" style={{ marginLeft: 6, fontSize: 9 }}>soon</span>}
        </button>
      ))}
    </div>
  )
}

function NotBuilt({ section }) {
  return (
    <div className="card" data-testid="ds-not-built" style={{ padding: 32, textAlign: 'center', marginTop: 16 }}>
      <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--pine-deep)', marginBottom: 8 }}>
        {section.label} — not built yet
      </div>
      <div className="text-low" style={{ fontSize: 13, maxWidth: 520, margin: '0 auto 16px' }}>
        {section.note}. This workspace will be armed to the local creative pipeline after the research phase.
      </div>
      <div className="text-low" style={{ fontSize: 12 }}>
        When built, every generate action will show a cost/quota preview and require confirmation.
      </div>
    </div>
  )
}

export default function DesignStudio() {
  const { toast } = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  // The studio also renders inside the workbench (U3), where it does NOT own the
  // URL. Embedded, its section lives in component state; on its own route it
  // stays driven by ?section=. Without this split, mounting the studio in a tab
  // navigated the whole shell to /design-studio.
  const embedded = !location.pathname.startsWith('/design-studio')
  const [embeddedSection, setEmbeddedSection] = useState('')
  const requested = embedded ? embeddedSection
    : (new URLSearchParams(location.search).get('section') || '')
  const sectionId = SECTIONS.some(s => s.id === requested) ? requested : 'canvas'
  const section = useMemo(() => SECTIONS.find(s => s.id === sectionId), [sectionId])

  const setSection = (id) => {
    if (embedded) {
      setEmbeddedSection(id)
      return
    }
    navigate(`/design-studio?section=${id}`, { replace: true })
  }

  useEffect(() => {
    if (embedded) return
    if (sectionId !== requested) {
      // Preserve the rest of the query (the merged pre-view rooms carry their
      // sub-view in ?view=; dropping it would silently reset the tab).
      const params = new URLSearchParams(location.search)
      params.set('section', sectionId)
      navigate(`/design-studio?${params.toString()}`, { replace: true })
    }
  }, [embedded, requested, sectionId, navigate, location.search])

  // Opt-in engine hook for browser harnesses (?engine=1).
  useEffect(() => { attachEngineHook() }, [])

  // One-time import of any pre-backend browser records into the tenant's
  // backend store. Idempotent, and it never deletes the local copy until the
  // server confirms the import.
  useEffect(() => {
    if (migrationDone()) return
    let cancelled = false
    migrateLocalStorage().then((r) => {
      if (cancelled || !r.ran) return
      const made = r.created ? (r.created.projects + r.created.assets + r.created.jobs) : 0
      if (made > 0) {
        toast(`Imported ${made} local record${made === 1 ? '' : 's'} into your workspace.`, 'info')
      }
    })
    return () => { cancelled = true }
  }, [toast])

  return (
    <PageLayout title="Design Studio" subtitle="One studio for every creative asset your Amazon listings need.">
      <SectionPicker active={sectionId} onChange={setSection} />
      {sectionId === 'projects' && (
        <div className="card" style={{ marginBottom: 16, padding: 16 }} data-testid="ds-quickstart">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <strong style={{ fontSize: 14 }}>Quick start</strong>
            <span className="pill pill-muted">guided first steps</span>
          </div>
          <div className="grid-3" style={{ gap: 10 }}>
            {[
              { label: 'Main image from a photo', note: 'Upload your photo; white-background check + export', to: 'listing-images' },
              { label: 'A+ set from a brief', note: 'Modules, alt text and placement instructions', to: 'aplus' },
              { label: 'Dieline & print pack', note: 'Layered SVG / PDF / project ZIP', to: 'dielines' },
            ].map(q => (
              <button key={q.to} className="card" onClick={() => setSection(q.to)}
                style={{ padding: 14, textAlign: 'left', cursor: 'pointer', fontFamily: 'var(--font-ui)', border: '1px solid var(--divider)' }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--pine-deep)' }}>{q.label}</div>
                <div className="text-low" style={{ fontSize: 11, marginTop: 2 }}>{q.note}</div>
              </button>
            ))}
          </div>
        </div>
      )}
      {sectionId === 'canvas' && <CanvasWorkspace onNavigateSection={setSection} />}
      {sectionId === 'projects' && <CreativeStudio />}
      {sectionId === 'listing-images' && <ListingImages />}
      {sectionId === 'aplus' && <APlus />}
      {sectionId === 'storefront' && <Storefront />}
      {sectionId === 'ads' && <Ads />}
      {sectionId === 'video-ugc' && <VideoUgc />}
      {sectionId === 'social' && <Social />}
      {sectionId === 'packaging' && <Packaging />}
      {sectionId === 'dielines' && <Dielines />}
      {sectionId === 'deliverables' && <Deliverables />}
      {sectionId === '3d-scene' && <ProductDesigner />}
      {!SECTIONS.some(s => s.id === sectionId) && <NotBuilt section={section} />}
    </PageLayout>
  )
}
