// The shell's tab state: which workspaces are open, which one the location
// belongs to, and the scroll offset each tab had when it was left.
//
// The location is the source of truth for the ACTIVE tab — a tab is not a
// second navigation history, so the browser Back button and a click on a tab
// produce the same state. What the hook owns is the open list (persisted in
// sessionStorage) and the per-tab scroll memory, which is what makes a switch
// feel like a tab switch instead of a remount.
//
// Mounted pages are deliberately NOT kept here: `ShellLayout` renders them
// (from `WorkspacePanels.jsx`) so they stay mounted while hidden, and this hook
// only tracks which of them has been visited so a tab is not mounted before it
// is first opened.

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import {
  TAB_STORAGE_KEY,
  closeTab as closeTabPure,
  openTab,
  parseTabs,
  sameTabs,
  serializeTabs,
  tabForPath,
  tabSummary,
} from './tabRoutes.js'

function readStore() {
  try { return sessionStorage.getItem(TAB_STORAGE_KEY) } catch { return null }
}

function writeStore(value) {
  try { sessionStorage.setItem(TAB_STORAGE_KEY, value) } catch { /* storage unavailable */ }
}

export default function useWorkspaceTabs(location, navigate) {
  const mainRef = useRef(null)
  const scrollRef = useRef(new Map())
  const [tabs, setTabs] = useState(() => parseTabs(readStore()).tabs)

  const current = tabForPath(location.pathname, location.search)
  const currentKey = current ? `${current.id}|${current.path}|${current.search}` : ''
  const activeId = current?.id || null

  // The location's tab exists in the render that first shows it, even before
  // the commit effect below writes it into the list.
  const visibleTabs = useMemo(
    () => (current ? openTab(tabs, current) : tabs),
    [tabs, currentKey], // eslint-disable-line react-hooks/exhaustive-deps
  )

  // Commit the location's tab into the open list (and re-point it when the
  // operator navigated inside the workspace).
  useLayoutEffect(() => {
    if (!current) return
    setTabs((prev) => {
      const next = openTab(prev, current)
      return sameTabs(prev, next) ? prev : next
    })
  }, [currentKey]) // eslint-disable-line react-hooks/exhaustive-deps

  // Write on commit, before paint: a tab switch may replace the whole shell
  // subtree (for example closing the last tab lands on /home), and an effect
  // scheduled after paint would not run on the instance being unmounted.
  useLayoutEffect(() => { writeStore(serializeTabs(tabs)) }, [tabs])

  // A tab mounts the first time it is opened, then stays mounted. Mounting all
  // of them at once made five workspaces start their effects together.
  const [visited, setVisited] = useState(() => new Set(current ? [current.id] : []))
  useEffect(() => {
    if (!current) return
    setVisited((prev) => {
      if (prev.has(current.id)) return prev
      const next = new Set(prev)
      next.add(current.id)
      return next
    })
  }, [currentKey]) // eslint-disable-line react-hooks/exhaustive-deps

  // Scroll memory. `.main-content` is the scroll container (app.css: overflow-y
  // auto) and it is shared by every tab, so it has to be re-pointed at the
  // incoming tab's offset.
  //
  // The offset is recorded FROM THE SCROLL EVENT, not read at switch time:
  // hiding the outgoing panel clamps the shared container to 0 before the
  // switch commits, so reading it there would store 0 and lose the position.
  const activeIdRef = useRef(activeId)
  activeIdRef.current = activeId
  const restoringRef = useRef(false)
  useEffect(() => {
    const el = mainRef.current
    if (!el) return undefined
    const onScroll = () => {
      if (restoringRef.current) return
      const id = activeIdRef.current
      if (id) scrollRef.current.set(id, el.scrollTop)
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [])

  // Two frames: the first lets the panel paint, the second applies the offset
  // once a lazily-loaded page has grown its height.
  useLayoutEffect(() => {
    const el = mainRef.current
    const target = activeId ? (scrollRef.current.get(activeId) || 0) : 0
    if (!el) return undefined
    restoringRef.current = true
    el.scrollTop = target
    let second = 0
    const first = requestAnimationFrame(() => {
      second = requestAnimationFrame(() => {
        if (mainRef.current === el && el.scrollTop !== target) el.scrollTop = target
        restoringRef.current = false
      })
    })
    return () => {
      cancelAnimationFrame(first)
      cancelAnimationFrame(second)
      restoringRef.current = false
    }
  }, [activeId])

  const activate = useCallback((tab) => {
    if (tab?.href) navigate(tab.href)
  }, [navigate])

  const close = useCallback((id) => {
    const result = closeTabPure(visibleTabs, id, activeId)
    scrollRef.current.delete(id)
    setTabs(result.tabs)
    // Persist BEFORE navigating: closing the last tab leaves this shell
    // subtree for /home, and the replacement reads its list from storage.
    writeStore(serializeTabs(result.tabs))
    if (result.nextPath) navigate(result.nextPath)
  }, [visibleTabs, activeId, navigate])

  const summary = useMemo(() => tabSummary({
    tabs: visibleTabs,
    activeTab: current,
    scrollTop: current ? (scrollRef.current.get(current.id) || 0) : 0,
  }), [visibleTabs, currentKey]) // eslint-disable-line react-hooks/exhaustive-deps

  return {
    tabs: visibleTabs,
    activeId,
    activeTab: current,
    visited,
    mainRef,
    summary,
    activate,
    close,
  }
}
