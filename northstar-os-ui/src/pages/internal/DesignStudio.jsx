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

const SECTIONS = [
  { id: 'projects', label: 'Projects', icon: 'stack', note: 'Project board and asset library', built: true },
  { id: 'listing-images', label: 'Listing Images', icon: 'image', note: 'Main, lifestyle, infographic modules', built: true },
  { id: 'aplus', label: 'A+ / Brand Story', icon: 'list', note: 'Amazon A+ modules and Brand Story cards', built: false },
  { id: 'storefront', label: 'Storefront', icon: 'store', note: 'Amazon Storefront pages and tiles', built: false },
  { id: 'ads', label: 'Ads', icon: 'target', note: 'Sponsored Brands, Display and social ad creatives', built: false },
  { id: 'video-ugc', label: 'Video & UGC Clips', icon: 'film', note: 'Product videos, UGC-style clips and hooks', built: false },
  { id: 'social', label: 'Social', icon: 'users', note: 'Social posts, carousels and stories', built: false },
  { id: 'packaging', label: 'Packaging & Mockups', icon: 'package', note: 'Packaging dielines and mockup renders', built: false },
  { id: '3d-scene', label: '3D Product Scene', icon: 'cube', note: 'Real 3D product scene composer', built: true },
]

function SectionPicker({ active, onChange }) {
  return (
    <div className="ds-section-picker" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
      {SECTIONS.map(s => (
        <button
          key={s.id}
          className={`btn btn-sm ${active === s.id ? 'btn-primary' : ''}`}
          title={s.note}
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
  const requested = new URLSearchParams(location.search).get('section') || ''
  const sectionId = SECTIONS.some(s => s.id === requested) ? requested : 'projects'
  const section = useMemo(() => SECTIONS.find(s => s.id === sectionId), [sectionId])

  const setSection = (id) => {
    navigate(`/design-studio?section=${id}`, { replace: true })
  }

  useEffect(() => {
    if (sectionId !== requested) {
      navigate(`/design-studio?section=${sectionId}`, { replace: true })
    }
  }, [requested, sectionId, navigate])

  return (
    <PageLayout title="Design Studio" subtitle="One studio for every creative asset your Amazon listings need.">
      <SectionPicker active={sectionId} onChange={setSection} />
      {sectionId === 'projects' && <CreativeStudio />}
      {sectionId === 'listing-images' && <ListingImages />}
      {sectionId === '3d-scene' && <ProductDesigner />}
      {sectionId !== 'projects' && sectionId !== 'listing-images' && sectionId !== '3d-scene' && <NotBuilt section={section} />}
    </PageLayout>
  )
}
