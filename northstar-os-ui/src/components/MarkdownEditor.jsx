import { useEffect, useRef, useState } from 'react'
import Markdown from './Markdown.jsx'

/**
 * Inline markdown editing (item 16): source and preview share ONE grid cell, so
 * toggling cannot shift the layout around it - the classic jank this item is
 * about. The mode is persisted per instance key.
 *
 * Editing keeps the caret and scroll of the textarea; the preview is re-parsed
 * on a short debounce so a 200-line document does not re-render on every key.
 */
export default function MarkdownEditor({
  value = '',
  onChange,
  storageKey = 'northstar.md.mode',
  rows = 12,
  label = 'Markdown editor',
}) {
  const [mode, setMode] = useState(() => {
    try { return localStorage.getItem(storageKey) || 'edit' } catch { return 'edit' }
  })
  const [draft, setDraft] = useState(value)
  const [preview, setPreview] = useState(value)
  const timer = useRef(null)

  useEffect(() => { setDraft(value) }, [value])

  useEffect(() => {
    try { localStorage.setItem(storageKey, mode) } catch { /* non-fatal */ }
  }, [mode, storageKey])

  useEffect(() => {
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setPreview(draft), 120)
    return () => clearTimeout(timer.current)
  }, [draft])

  const onInput = (event) => {
    setDraft(event.target.value)
    if (onChange) onChange(event.target.value)
  }

  return (
    <div className="md-editor" data-mode={mode}>
      <div className="md-editor__bar">
        <div className="md-editor__tabs" role="tablist" aria-label={label}>
          <button
            type="button" role="tab" aria-selected={mode === 'edit'}
            className={`md-editor__tab ${mode === 'edit' ? 'is-active' : ''}`}
            onClick={() => setMode('edit')}
          >
            Write
          </button>
          <button
            type="button" role="tab" aria-selected={mode === 'preview'}
            className={`md-editor__tab ${mode === 'preview' ? 'is-active' : ''}`}
            onClick={() => setMode('preview')}
          >
            Preview
          </button>
        </div>
        <span className="md-editor__count">{draft.length} chars</span>
      </div>

      <div className="md-editor__pane">
        {mode === 'edit' ? (
          <textarea
            className="md-editor__input"
            aria-label={label}
            rows={rows}
            value={draft}
            onChange={onInput}
            spellCheck
          />
        ) : (
          <div className="md-editor__preview" aria-live="polite">
            <Markdown source={preview} />
          </div>
        )}
      </div>
    </div>
  )
}
