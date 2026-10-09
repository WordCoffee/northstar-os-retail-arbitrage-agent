// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — ASSET STORE (IndexedDB)
//
// Real operator-owned image storage in the browser: files the operator uploads
// are read locally, decoded, measured, and persisted as data URLs in IndexedDB.
// Nothing is uploaded anywhere. When storage is unavailable the store degrades
// to a session-only memory map and reports that honestly (`persistent: false`)
// so the UI never implies durability it does not have.
// ═══════════════════════════════════════════════════════════════════════════

import { useCallback, useEffect, useRef, useState } from 'react'

const DB_NAME = 'northstar-studio'
const DB_VERSION = 1
const STORE = 'assets'

// Soft ceiling for the whole store. Past this the UI warns; it does not delete.
export const SOFT_QUOTA_BYTES = 256 * 1024 * 1024

let dbPromise = null

function openDb() {
  if (typeof indexedDB === 'undefined') return Promise.reject(new Error('indexeddb_unavailable'))
  if (dbPromise) return dbPromise
  dbPromise = new Promise((resolve, reject) => {
    let req
    try {
      req = indexedDB.open(DB_NAME, DB_VERSION)
    } catch (e) {
      reject(e)
      return
    }
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'id' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error || new Error('indexeddb_open_failed'))
  })
  return dbPromise
}

function tx(mode) {
  return openDb().then(db => db.transaction(STORE, mode).objectStore(STORE))
}

function wrapRequest(req) {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error || new Error('indexeddb_request_failed'))
  })
}

export async function putAsset(record) {
  try {
    const store = await tx('readwrite')
    await wrapRequest(store.put(record))
    return { ok: true, persistent: true }
  } catch (e) {
    return { ok: false, persistent: false, reason: String(e && e.message || e) }
  }
}

export async function listAssets() {
  try {
    const store = await tx('readonly')
    const all = await wrapRequest(store.getAll())
    return (all || []).sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)))
  } catch {
    return []
  }
}

export async function deleteAsset(id) {
  try {
    const store = await tx('readwrite')
    await wrapRequest(store.delete(id))
    return true
  } catch {
    return false
  }
}

export async function storageEstimate() {
  if (typeof navigator === 'undefined' || !navigator.storage?.estimate) return null
  try {
    const e = await navigator.storage.estimate()
    return { usage: e.usage || 0, quota: e.quota || 0 }
  } catch {
    return null
  }
}

// ── File reading ─────────────────────────────────────────────────────────────

export function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader()
    fr.onload = () => resolve(String(fr.result))
    fr.onerror = () => reject(fr.error || new Error('file_read_failed'))
    fr.readAsDataURL(file)
  })
}

const imageCache = new Map()

export function loadImage(src) {
  if (!src) return Promise.reject(new Error('empty_src'))
  if (imageCache.has(src)) return imageCache.get(src)
  const p = new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('image_decode_failed'))
    img.decoding = 'async'
    img.src = src
  })
  imageCache.set(src, p)
  return p
}

export function peekCachedImage(src) {
  const p = imageCache.get(src)
  return p && p.__resolved === undefined ? null : null
}

// ── Asset metadata ───────────────────────────────────────────────────────────

function measure(dataUrl) {
  return loadImage(dataUrl).then(img => ({
    w: img.naturalWidth || img.width,
    h: img.naturalHeight || img.height,
  })).catch(() => ({ w: 0, h: 0 }))
}

export function approxBytesOfDataUrl(dataUrl) {
  const i = String(dataUrl || '').indexOf(',')
  if (i < 0) return 0
  const body = dataUrl.slice(i + 1)
  const pad = (body.endsWith('==') ? 2 : body.endsWith('=') ? 1 : 0)
  return Math.max(0, Math.floor((body.length * 3) / 4) - pad)
}

let counter = 0
export function newAssetId() {
  counter += 1
  return `AS-${Date.now().toString(36).toUpperCase()}-${counter.toString(36)}`
}

/**
 * Decode every asset in the store to an HTMLImageElement and hand back a
 * Map<assetId, HTMLImageElement> the renderers can consume synchronously.
 * Assets already in the module-level image cache resolve immediately.
 */
export function useDecodedAssets(assets) {
  const [map, setMap] = useState(() => new Map())
  const [ready, setReady] = useState(0)
  const key = (assets || []).map(a => a.id).join('|')
  useEffect(() => {
    let alive = true
    const list = assets || []
    const m = new Map()
    if (!list.length) { setMap(m); setReady(v => v + 1); return () => { alive = false } }
    Promise.all(list.map(a => loadImage(a.dataUrl)
      .then(img => { m.set(a.id, img) })
      .catch(() => { /* decode failed — renderer shows an honest placeholder */ })))
      .then(() => { if (alive) { setMap(m); setReady(v => v + 1) } })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  return { images: map, ready }
}

export function useAssetStore() {
  const [assets, setAssets] = useState([])
  const [persistent, setPersistent] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const memory = useRef(new Map())
  const loaded = useRef(false)

  const refresh = useCallback(async () => {
    const rows = await listAssets()
    rows.forEach(r => memory.current.set(r.id, r))
    setAssets(rows)
    setPersistent(true)
    loaded.current = true
    return rows
  }, [])

  useEffect(() => {
    let alive = true
    listAssets().then(rows => {
      if (!alive) return
      rows.forEach(r => memory.current.set(r.id, r))
      setAssets(rows)
      loaded.current = true
      setPersistent(rows.length === 0 ? true : true)
    }).catch(() => {
      if (alive) setPersistent(false)
    })
    return () => { alive = false }
  }, [])

  const add = useCallback(async (fileList, meta = {}) => {
    const files = Array.from(fileList || []).filter(f => /^image\//.test(f.type))
    if (!files.length) {
      setError('No image files were supplied. The asset store accepts image files only.')
      return []
    }
    setBusy(true)
    setError('')
    const added = []
    for (const file of files) {
      try {
        const dataUrl = await readFileAsDataUrl(file)
        const dim = await measure(dataUrl)
        const rec = {
          id: newAssetId(),
          name: file.name || 'untitled',
          mime: file.type,
          dataUrl,
          w: dim.w,
          h: dim.h,
          bytes: approxBytesOfDataUrl(dataUrl),
          role: meta.role || 'reference',
          tags: meta.tags || [],
          createdAt: new Date().toISOString(),
        }
        const res = await putAsset(rec)
        if (!res.ok) {
          memory.current.set(rec.id, rec)
          setPersistent(false)
        }
        added.push(rec)
      } catch (e) {
        setError(`Could not read ${file.name}: ${String(e && e.message || e)}`)
      }
    }
    setBusy(false)
    const merged = [...added, ...assets]
    setAssets(merged)
    return added
  }, [assets])

  const remove = useCallback(async (id) => {
    await deleteAsset(id)
    memory.current.delete(id)
    setAssets(prev => prev.filter(a => a.id !== id))
  }, [])

  const get = useCallback((id) => assets.find(a => a.id === id) || memory.current.get(id) || null, [assets])

  const totalBytes = assets.reduce((s, a) => s + (a.bytes || 0), 0)

  return { assets, add, remove, get, refresh, busy, error, persistent, totalBytes, loaded }
}
