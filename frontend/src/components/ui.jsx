// Small shared UI pieces: loading skeletons, empty states, error banner.
import { errorMessage } from '../api'

export function Skeleton({ className = 'h-4 w-full' }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />
}

export function SkeletonCard({ lines = 3 }) {
  return (
    <div className="card p-5 space-y-3" role="status" aria-label="Loading">
      <Skeleton className="h-5 w-1/3" />
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={`h-4 ${i === lines - 1 ? 'w-2/3' : 'w-full'}`} />
      ))}
    </div>
  )
}

export function EmptyState({ icon = '🌱', title, children, action }) {
  return (
    <div className="card p-8 text-center">
      <div className="text-4xl mb-2" aria-hidden="true">{icon}</div>
      <h3 className="font-semibold text-slate-800">{title}</h3>
      {children && <p className="text-sm text-slate-500 mt-1 max-w-md mx-auto">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

// "backend not reachable" when there is no response at all, otherwise the server's own message.
export function friendlyError(e) {
  if (!e?.response) return 'Backend not reachable. Check your connection (the server may be waking up) and try again.'
  return errorMessage(e)
}

export function ErrorBanner({ error, onRetry }) {
  if (!error) return null
  const text = typeof error === 'string' ? error : friendlyError(error)
  return (
    <div role="alert" className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm flex items-center gap-3">
      <span className="flex-1">{text}</span>
      {onRetry && (
        <button type="button" onClick={onRetry} className="underline hover:text-red-600">Retry</button>
      )}
    </div>
  )
}
