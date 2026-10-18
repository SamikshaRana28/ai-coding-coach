// Collapsible list of the hints the student has already unlocked (level 1 first).
// Purely presentational: ProblemPage owns the data and the open/closed state.

const LEVEL_TITLES = {
  1: 'A small nudge',
  2: 'The approach',
  3: 'Outline (pseudo-code)',
}

export default function HintPanel({ hints, maxLevel = 3, open, onToggle }) {
  if (!hints || hints.length === 0) return null
  return (
    <div className="border border-amber-200 bg-amber-50 rounded-lg">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="w-full flex items-center justify-between px-3 py-2 text-sm font-medium text-amber-900 rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
      >
        <span>💡 Hints unlocked ({hints.length}/{maxLevel})</span>
        <span aria-hidden="true">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <ol className="px-3 pb-3 space-y-3">
          {hints.map((h) => (
            <li key={h.level} className="text-sm text-slate-800">
              <div className="text-xs font-semibold uppercase tracking-wide text-amber-800">
                Hint {h.level} · {LEVEL_TITLES[h.level] || ''}
              </div>
              {/* plain text node: whatever the model wrote is never rendered as HTML */}
              <p className="whitespace-pre-wrap mt-0.5">{h.text}</p>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
