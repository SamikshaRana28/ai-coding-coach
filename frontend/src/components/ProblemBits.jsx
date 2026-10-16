// Small presentational pieces shared by the Problems list and the Problem page.

const DIFFICULTY_STYLES = {
  Easy: 'bg-green-100 text-green-700',
  Medium: 'bg-amber-100 text-amber-700',
  Hard: 'bg-red-100 text-red-700',
}

export function DifficultyBadge({ difficulty }) {
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${DIFFICULTY_STYLES[difficulty] || 'bg-slate-100 text-slate-700'}`}>
      {difficulty}
    </span>
  )
}

export function TopicChips({ topics = [] }) {
  return (
    <div className="flex flex-wrap gap-1">
      {topics.map((t) => (
        <span key={t} className="px-2 py-0.5 rounded-full text-xs bg-slate-100 text-slate-600 border border-slate-200">
          {t}
        </span>
      ))}
    </div>
  )
}

export const STATUS_LABELS = { todo: 'Todo', attempted: 'Attempted', solved: 'Solved' }

// Inline SVGs (no icon-library dependency): empty circle / half-filled / check
export function StatusIcon({ status, className = 'w-5 h-5' }) {
  const label = STATUS_LABELS[status] || STATUS_LABELS.todo
  const common = {
    className,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    role: 'img',
    'aria-label': label,
  }
  if (status === 'solved') {
    return (
      <svg {...common} className={`${className} text-green-600`}>
        <title>{label}</title>
        <circle cx="12" cy="12" r="9" />
        <path d="M8 12.5l3 3 5-6" />
      </svg>
    )
  }
  if (status === 'attempted') {
    return (
      <svg {...common} className={`${className} text-amber-500`}>
        <title>{label}</title>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor" stroke="none" />
      </svg>
    )
  }
  return (
    <svg {...common} className={`${className} text-slate-300`}>
      <title>{label}</title>
      <circle cx="12" cy="12" r="9" />
    </svg>
  )
}
