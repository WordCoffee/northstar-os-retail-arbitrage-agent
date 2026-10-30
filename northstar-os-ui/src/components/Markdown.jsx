import { parseBlocks, parseInline } from '../lib/markdown.js'
import './markdown.css'

/** Inline tokens -> elements. No dangerouslySetInnerHTML anywhere. */
function Inline({ text }) {
  return parseInline(text).map((tok, i) => {
    if (tok.type === 'code') return <code key={i}>{tok.value}</code>
    if (tok.type === 'strong') return <strong key={i}>{tok.value}</strong>
    if (tok.type === 'em') return <em key={i}>{tok.value}</em>
    if (tok.type === 'link') {
      return <a key={i} href={tok.href} target="_blank" rel="noreferrer noopener">{tok.value}</a>
    }
    return <span key={i}>{tok.value}</span>
  })
}

/** Rendered markdown. Safe subset only - see lib/markdown.js. */
export default function Markdown({ source = '' }) {
  const blocks = parseBlocks(source)
  if (blocks.length === 0) return <div className="md md--empty" aria-hidden="true" />
  return (
    <div className="md">
      {blocks.map((block, i) => {
        if (block.type === 'h') {
          const Tag = `h${Math.min(6, Math.max(1, block.level))}`
          return <Tag key={i}><Inline text={block.text} /></Tag>
        }
        if (block.type === 'code') {
          return (
            <pre key={i} className="md__code" data-lang={block.lang || undefined}>
              <code>{block.text}</code>
            </pre>
          )
        }
        if (block.type === 'quote') {
          return <blockquote key={i}><Inline text={block.text} /></blockquote>
        }
        if (block.type === 'hr') return <hr key={i} />
        if (block.type === 'list') {
          const Tag = block.ordered ? 'ol' : 'ul'
          return (
            <Tag key={i}>
              {block.items.map((item, j) => <li key={j}><Inline text={item} /></li>)}
            </Tag>
          )
        }
        return <p key={i}><Inline text={block.text} /></p>
      })}
    </div>
  )
}
