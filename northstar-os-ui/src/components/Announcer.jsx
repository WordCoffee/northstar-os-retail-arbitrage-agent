import { useEffect, useState } from 'react'
import { subscribe } from '../lib/announce.js'

/**
 * Live regions (item 12). Mount ONCE, near the shell root.
 *
 * Two regions because a single one cannot change politeness: an assertive
 * message in a polite region is read at the wrong time and vice versa. Both are
 * visually hidden but present in the accessibility tree, and both are cleared
 * on a timer so the same message can be announced twice in a row.
 */
const HIDE = {
  position: 'absolute',
  width: 1,
  height: 1,
  margin: -1,
  padding: 0,
  overflow: 'hidden',
  clip: 'rect(0 0 0 0)',
  whiteSpace: 'nowrap',
  border: 0,
}

export default function Announcer({ clearAfterMs = 7000 }) {
  const [polite, setPolite] = useState('')
  const [assertive, setAssertive] = useState('')

  useEffect(() => subscribe(({ text, assertive: loud }) => {
    const set = loud ? setAssertive : setPolite
    // Clear first so a repeated identical string still triggers a mutation.
    set('')
    const timer = setTimeout(() => set(text), 30)
    const clear = setTimeout(() => set(''), clearAfterMs)
    return () => { clearTimeout(timer); clearTimeout(clear) }
  }), [clearAfterMs])

  return (
    <>
      <div aria-live="polite" aria-atomic="true" role="status" style={HIDE}>
        {polite}
      </div>
      <div aria-live="assertive" aria-atomic="true" role="alert" style={HIDE}>
        {assertive}
      </div>
    </>
  )
}
