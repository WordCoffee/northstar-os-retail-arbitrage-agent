// ═══════════════════════════════════════════════════════════════════════════
// ASSET FILE SOURCE
//
// Studio files live behind the strict session dependency (studio_account), and
// that dependency accepts either the hosted session cookie OR — in local
// development only — the X-User-Id identity shim. An <img>/<video>/<object>
// element cannot send that header, so in dev every rendered artifact came back
// 401 and the chat showed "Unavailable — the file could not be loaded." even
// though the render had succeeded.
//
// In dev we therefore fetch the bytes ourselves (with the same shim headers the
// rest of the chat uses) and hand the element an object URL. In a built bundle
// LOCAL_DEV is compiled out, the cookie travels on the element request as usual,
// and this returns the plain URL — no extra request, no behaviour change.
// ═══════════════════════════════════════════════════════════════════════════

import { useEffect, useState } from 'react'
import { LOCAL_DEV } from '../foundation/dev.js'

export function assetFileUrl(assetId) {
  return `/api/design-studio/assets/${assetId}/file`
}

function devShimHeaders() {
  const h = {}
  try {
    const s = JSON.parse(localStorage.getItem('ns-dev-session') || 'null')
    if (s && s.userId) {
      h['X-User-Id'] = s.userId
      if (s.orgId) h['X-Org-Id'] = s.orgId
      if (s.role) h['X-Role'] = s.role
    }
  } catch { /* storage unavailable - hosted cookie auth is used */ }
  return h
}

export async function saveAsset(assetId, name) {
  const url = assetFileUrl(assetId)
  if (!LOCAL_DEV) {
    const a = document.createElement('a')
    a.href = url
    a.download = name || 'asset'
    a.click()
    return
  }
  const r = await fetch(url, { credentials: 'include', headers: devShimHeaders() })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  const objectUrl = URL.createObjectURL(await r.blob())
  const a = document.createElement('a')
  a.href = objectUrl
  a.download = name || 'asset'
  a.click()
  setTimeout(() => URL.revokeObjectURL(objectUrl), 10000)
}

/** Resolve the URL an <img>/<video>/<object> should use for a studio asset. */
export function useAssetSrc(assetId) {
  const direct = assetId ? assetFileUrl(assetId) : null
  const [src, setSrc] = useState(LOCAL_DEV ? null : direct)

  useEffect(() => {
    if (!LOCAL_DEV || !assetId) { setSrc(direct); return undefined }
    let cancelled = false
    let objectUrl = null
    fetch(assetFileUrl(assetId), { credentials: 'include', headers: devShimHeaders() })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.blob()
      })
      .then((blob) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setSrc(objectUrl)
      })
      .catch(() => { if (!cancelled) setSrc(null) })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [assetId, direct])

  return src
}
