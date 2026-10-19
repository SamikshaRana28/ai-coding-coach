// "Where to focus": weak topics + patterns to study, honest when there is little data.
import { useEffect, useState } from 'react'
import { getFocus, errorMessage } from '../api'

const label = (t) => (t === 'dp' ? 'DP' : t.charAt(0).toUpperCase() + t.slice(1))

export default function FocusCard() {
  const [state, setState] = useState({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    getFocus()
      .then((res) => { if (!cancelled) setState({ status: 'ok', data: res.data }) })
      .catch((e) => { if (!cancelled) setState({ status: 'error', message: errorMessage(e) }) })
    return () => { cancelled = true }
  }, [])

  const card = 'bg-white rounded-xl p-6 border border-slate-200'
  if (state.status === 'loading') return <div className={`${card} animate-pulse text-slate-400`}>Loading focus areas…</div>
  if (state.status === 'error') return <div className={`${card} text-red-600 text-sm`}>Could not load focus areas: {state.message}</div>

  const { focus, patterns, note, source } = state.data
  return (
    <section className={`${card} space-y-3`} aria-label="Where to focus">
      <h2 className="font-bold text-lg">Where to focus</h2>
      {note && <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">{note}</p>}
      <ul className="space-y-2">
        {focus.map((f) => (
          <li key={f.topic} className="text-sm">
            <span className="font-semibold">{label(f.topic)}</span>
            <span className="text-slate-500">: {f.reason}</span>
          </li>
        ))}
      </ul>
      {patterns.length > 0 && (
        <div>
          <div className="text-xs text-slate-500 mb-1">Patterns to study</div>
          <div className="flex flex-wrap gap-1">
            {patterns.map((p) => (
              <span key={p} className="px-2 py-0.5 rounded-full text-xs bg-blue-50 text-blue-700 border border-blue-100">{p}</span>
            ))}
          </div>
        </div>
      )}
      <p className="text-[11px] text-slate-400">
        {source === 'model+stats' ? 'From your stats and the weak-topic model.' : 'From your solved-problem stats.'}
      </p>
    </section>
  )
}
