import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { listProblems, errorMessage } from '../api'
import { DifficultyBadge, StatusIcon, TopicChips } from '../components/ProblemBits'

const TOPICS = ['arrays', 'dp', 'graphs', 'trees', 'strings', 'math', 'others']
const PAGE_SIZES = [10, 20, 50]
const DEFAULT_PAGE_SIZE = 20

// [1, 'gap', 4, 5, 6, 'gap', 25] style window around the current page
function pageWindow(page, totalPages) {
  const wanted = new Set([1, totalPages])
  for (let p = page - 2; p <= page + 2; p++) if (p >= 1 && p <= totalPages) wanted.add(p)
  const sorted = [...wanted].sort((a, b) => a - b)
  const out = []
  sorted.forEach((p, i) => {
    if (i > 0 && p - sorted[i - 1] > 1) out.push('gap')
    out.push(p)
  })
  return out
}

export default function Problems() {
  const navigate = useNavigate()
  // Filters + page live in the URL, so Back from a problem returns to the same view.
  const [params, setParams] = useSearchParams()
  const q = params.get('q') || ''
  const difficulty = params.get('difficulty') || ''
  const topic = params.get('topic') || ''
  const status = params.get('status') || ''
  const page = Math.max(1, parseInt(params.get('page') || '1', 10) || 1)
  const requestedSize = parseInt(params.get('page_size') || '', 10)
  const pageSize = PAGE_SIZES.includes(requestedSize) ? requestedSize : DEFAULT_PAGE_SIZE

  const [searchInput, setSearchInput] = useState(q)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Functional update: safe even when called from a stale (debounced) closure.
  const update = (changes, { keepPage = false } = {}) => {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        Object.entries(changes).forEach(([key, value]) => {
          if (value) next.set(key, String(value))
          else next.delete(key)
        })
        if (!keepPage) next.delete('page')
        return next
      },
      { replace: true },
    )
  }

  // Debounce the search box (300 ms) before it hits the URL / the API.
  useEffect(() => {
    if (searchInput === q) return undefined
    const timer = setTimeout(() => update({ q: searchInput }), 300)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchInput])

  // Keep the box in sync when the URL changes from outside (Back button, Clear).
  useEffect(() => {
    setSearchInput(q)
  }, [q])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    listProblems({
      search: q || undefined,
      difficulty: difficulty || undefined,
      topic: topic || undefined,
      status: status || undefined,
      page,
      page_size: pageSize,
    })
      .then((res) => {
        if (!cancelled) setData(res.data)
      })
      .catch((e) => {
        if (!cancelled) setError(errorMessage(e))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [q, difficulty, topic, status, page, pageSize])

  // A page past the end (stale URL, or filters shrank the result set): go back to page 1.
  useEffect(() => {
    if (data && data.items.length === 0 && page > 1) update({ page: 1 }, { keepPage: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data])

  const hasFilters = Boolean(q || difficulty || topic || status)
  const clearFilters = () => {
    setSearchInput('')
    setParams({}, { replace: true })
  }

  const items = data?.items || []
  const total = data?.total ?? 0
  const totalPages = data?.total_pages ?? 1
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1
  const to = Math.min(page * pageSize, total)

  const selectClass = 'border border-slate-300 rounded-lg px-3 py-2 bg-white text-sm'

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">🧩 Problems</h1>
        <p className="text-slate-500 mt-1">
          Pick a question, solve it in the editor and get an AI review. Your status is tracked.
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        <input
          className="flex-1 min-w-[220px] border border-slate-300 rounded-lg px-4 py-2"
          placeholder="Search problems by title…"
          aria-label="Search problems"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
        />
        <select
          className={selectClass}
          aria-label="Filter by difficulty"
          value={difficulty}
          onChange={(e) => update({ difficulty: e.target.value })}
        >
          <option value="">All difficulties</option>
          <option value="Easy">Easy</option>
          <option value="Medium">Medium</option>
          <option value="Hard">Hard</option>
        </select>
        <select
          className={selectClass}
          aria-label="Filter by topic"
          value={topic}
          onChange={(e) => update({ topic: e.target.value })}
        >
          <option value="">All topics</option>
          {TOPICS.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select
          className={selectClass}
          aria-label="Filter by status"
          value={status}
          onChange={(e) => update({ status: e.target.value })}
        >
          <option value="">All statuses</option>
          <option value="todo">Todo</option>
          <option value="attempted">Attempted</option>
          <option value="solved">Solved</option>
        </select>
        {hasFilters && (
          <button onClick={clearFilters} className="text-sm text-blue-600 hover:underline px-2">
            Clear filters
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm">
          Could not load problems: {error}. Is the backend running and seeded?
        </div>
      )}

      <div className={`bg-white rounded-xl border border-slate-200 overflow-hidden transition-opacity ${loading && data ? 'opacity-60' : ''}`}>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-500 text-left">
            <tr>
              <th className="px-4 py-3 w-12">Status</th>
              <th className="px-4 py-3">Title</th>
              <th className="px-4 py-3 w-28">Difficulty</th>
              <th className="px-4 py-3">Topics</th>
              <th className="px-4 py-3 w-28 text-right">Acceptance</th>
            </tr>
          </thead>
          <tbody>
            {items.map((p) => (
              <tr
                key={p.id}
                onClick={() => navigate(`/problems/${p.id}`)}
                className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer"
              >
                <td className="px-4 py-3"><StatusIcon status={p.status} /></td>
                <td className="px-4 py-3">
                  <Link
                    to={`/problems/${p.id}`}
                    onClick={(e) => e.stopPropagation()}
                    className="font-medium text-slate-800 hover:text-blue-600"
                  >
                    {p.title}
                  </Link>
                </td>
                <td className="px-4 py-3"><DifficultyBadge difficulty={p.difficulty} /></td>
                <td className="px-4 py-3"><TopicChips topics={p.topics} /></td>
                <td className="px-4 py-3 text-right text-slate-500">
                  {p.acceptance_rate == null ? '—' : `${p.acceptance_rate.toFixed(1)}%`}
                </td>
              </tr>
            ))}
            {!loading && !error && items.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-12 text-center text-slate-400">
                  {hasFilters ? 'No problems match these filters.' : 'No problems yet — run the seed script (see README).'}
                </td>
              </tr>
            )}
            {loading && !data && (
              <tr>
                <td colSpan={5} className="px-4 py-12 text-center text-slate-400 animate-pulse">
                  Loading problems…
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-500">
        <span>
          {total > 0 ? `Showing ${from}–${to} of ${total}` : 'No results'}
        </span>

        <div className="flex items-center gap-1">
          <button
            onClick={() => update({ page: page - 1 }, { keepPage: true })}
            disabled={page <= 1}
            className="px-3 py-1 rounded border border-slate-300 bg-white disabled:opacity-40"
          >
            Prev
          </button>
          {pageWindow(page, totalPages).map((p, i) =>
            p === 'gap' ? (
              <span key={`gap-${i}`} className="px-1">…</span>
            ) : (
              <button
                key={p}
                onClick={() => update({ page: p }, { keepPage: true })}
                aria-current={p === page ? 'page' : undefined}
                className={`px-3 py-1 rounded border ${
                  p === page ? 'bg-blue-600 text-white border-blue-600' : 'bg-white border-slate-300 hover:bg-slate-50'
                }`}
              >
                {p}
              </button>
            ),
          )}
          <button
            onClick={() => update({ page: page + 1 }, { keepPage: true })}
            disabled={page >= totalPages}
            className="px-3 py-1 rounded border border-slate-300 bg-white disabled:opacity-40"
          >
            Next
          </button>
        </div>

        <label className="flex items-center gap-2">
          Per page
          <select
            className="border border-slate-300 rounded px-2 py-1 bg-white"
            value={pageSize}
            onChange={(e) => update({ page_size: e.target.value === String(DEFAULT_PAGE_SIZE) ? '' : e.target.value })}
          >
            {PAGE_SIZES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>
      </div>
    </div>
  )
}
