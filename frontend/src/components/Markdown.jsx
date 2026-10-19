// Tiny, dependency-free, XSS-safe markdown renderer for chat messages.
// Supports: ``` code blocks, `inline code`, **bold**, *italic*, - / * / 1. lists, # headings, links (http/https only).
// Everything becomes React elements (never dangerouslySetInnerHTML), so model output cannot inject HTML.
import { Fragment, useState } from 'react'

const INLINE = /(`[^`\n]+`|\*\*[^*\n]+\*\*|\*[^*\n]+\*|\[[^\]\n]+\]\(https?:\/\/[^)\s]+\))/g

function inline(text, keyBase) {
  return text.split(INLINE).map((part, i) => {
    const key = `${keyBase}-${i}`
    if (!part) return null
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
      return <code key={key} className="bg-elevated border border-line rounded px-1 py-0.5 text-[0.85em] font-mono">{part.slice(1, -1)}</code>
    }
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) return <strong key={key}>{part.slice(2, -2)}</strong>
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) return <em key={key}>{part.slice(1, -1)}</em>
    const link = part.match(/^\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)$/)
    if (link) {
      return <a key={key} href={link[2]} target="_blank" rel="noopener noreferrer" className="text-blue-400 underline">{link[1]}</a>
    }
    return <Fragment key={key}>{part}</Fragment>
  })
}

function CodeBlock({ code, lang }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch { /* clipboard blocked: ignore */ }
  }
  return (
    <div className="my-2 rounded-lg border border-line bg-canvas overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1 text-[11px] text-slate-400 border-b border-line">
        <span>{lang || 'code'}</span>
        <button type="button" onClick={copy} className="hover:text-slate-800">{copied ? 'Copied' : 'Copy'}</button>
      </div>
      <pre className="p-3 overflow-x-auto text-xs leading-relaxed font-mono text-slate-800"><code>{code}</code></pre>
    </div>
  )
}

export default function Markdown({ text = '' }) {
  const lines = String(text).replace(/\r\n/g, '\n').split('\n')
  const out = []
  let i = 0
  let k = 0
  while (i < lines.length) {
    const line = lines[i]
    const fence = line.match(/^\s*```(\w*)\s*$/)
    if (fence) {
      const buf = []
      i += 1
      while (i < lines.length && !/^\s*```\s*$/.test(lines[i])) { buf.push(lines[i]); i += 1 }
      i += 1                                              // closing fence (or end of text while streaming)
      out.push(<CodeBlock key={k++} code={buf.join('\n')} lang={fence[1]} />)
      continue
    }
    if (/^\s*([-*])\s+/.test(line) || /^\s*\d+\.\s+/.test(line)) {
      const ordered = /^\s*\d+\.\s+/.test(line)
      const items = []
      while (i < lines.length && (ordered ? /^\s*\d+\.\s+/ : /^\s*([-*])\s+/).test(lines[i])) {
        items.push(lines[i].replace(ordered ? /^\s*\d+\.\s+/ : /^\s*[-*]\s+/, ''))
        i += 1
      }
      const Tag = ordered ? 'ol' : 'ul'
      out.push(
        <Tag key={k++} className={`${ordered ? 'list-decimal' : 'list-disc'} pl-5 my-1 space-y-0.5`}>
          {items.map((it, j) => <li key={j}>{inline(it, `${k}-${j}`)}</li>)}
        </Tag>,
      )
      continue
    }
    const h = line.match(/^(#{1,4})\s+(.*)$/)
    if (h) {
      out.push(<p key={k++} className="font-semibold mt-2">{inline(h[2], `h${k}`)}</p>)
      i += 1
      continue
    }
    if (!line.trim()) { i += 1; continue }
    const para = []
    while (i < lines.length && lines[i].trim() && !/^\s*```/.test(lines[i]) && !/^\s*([-*]|\d+\.)\s+/.test(lines[i]) && !/^#{1,4}\s/.test(lines[i])) {
      para.push(lines[i]); i += 1
    }
    out.push(<p key={k++} className="my-1 break-words">{para.map((l, j) => <Fragment key={j}>{j > 0 && <br />}{inline(l, `p${k}-${j}`)}</Fragment>)}</p>)
  }
  return <div className="space-y-0.5">{out}</div>
}
