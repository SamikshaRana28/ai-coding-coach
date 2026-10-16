import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Editor from '@monaco-editor/react'
import {
  getProblem, submitProblem, markProblemSolved, getRecommendations, errorMessage,
} from '../api'
import { DifficultyBadge, StatusIcon, TopicChips, STATUS_LABELS } from '../components/ProblemBits'
import ReviewPanel from '../components/ReviewPanel'

const LANGUAGES = [
  { value: 'python', label: 'Python' },
  { value: 'javascript', label: 'JavaScript' },
  { value: 'java', label: 'Java' },
  { value: 'cpp', label: 'C++' },
]

const STARTERS = {
  python: 'class Solution:\n    def solve(self):\n        # write your solution here\n        pass\n',
  javascript: '/**\n * Write your solution here\n */\nfunction solve() {\n\n}\n',
  java: 'class Solution {\n    public void solve() {\n        // write your solution here\n    }\n}\n',
  cpp: 'class Solution {\npublic:\n    void solve() {\n        // write your solution here\n    }\n};\n',
}
const isStarter = (code) => Object.values(STARTERS).includes(code)

// The backend stores one last_code per problem (no language), so remember the preferred
// language in the browser instead; most people stick to one.
const LANGUAGE_KEY = 'acc:language'
function loadLanguage() {
  try {
    const saved = localStorage.getItem(LANGUAGE_KEY)
    if (LANGUAGES.some((l) => l.value === saved)) return saved
  } catch { /* storage unavailable */ }
  return 'python'
}
function saveLanguage(value) {
  try { localStorage.setItem(LANGUAGE_KEY, value) } catch { /* ignore */ }
}

export default function ProblemPage() {
  const { id } = useParams()
  const [problem, setProblem] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [language, setLanguage] = useState(loadLanguage)
  const [code, setCode] = useState('')
  const [result, setResult] = useState(null)          // submit response: { review, status, clean, newly_solved, ... }
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState(null)
  const [marking, setMarking] = useState(false)
  const [similar, setSimilar] = useState({ state: 'loading', items: [] })

  // Load the problem (and the student's last code) whenever the URL id changes.
  useEffect(() => {
    let cancelled = false
    setProblem(null)
    setLoadError(null)
    setResult(null)
    setSubmitError(null)
    getProblem(id)
      .then((res) => {
        if (cancelled) return
        setProblem(res.data)
        setCode(res.data.last_code ?? STARTERS[loadLanguage()])
      })
      .catch((e) => {
        if (cancelled) return
        setLoadError(e.response?.status === 404 ? 'Problem not found.' : errorMessage(e))
      })
    return () => {
      cancelled = true
    }
  }, [id])

  // "Similar questions" come from /recommend, keyed on the problem title.
  const title = problem?.title
  useEffect(() => {
    if (!title) return undefined
    let cancelled = false
    setSimilar({ state: 'loading', items: [] })
    getRecommendations({ title })
      .then((res) => {
        if (!cancelled) setSimilar({ state: 'ok', items: res.data.similar_questions || [] })
      })
      .catch(() => {
        if (!cancelled) setSimilar({ state: 'error', items: [] })
      })
    return () => {
      cancelled = true
    }
  }, [title])

  const onLanguageChange = (next) => {
    // swap the starter template only if the student hasn't written anything
    setCode((prev) => (isStarter(prev) ? STARTERS[next] : prev))
    setLanguage(next)
    saveLanguage(next)
  }

  const handleSubmit = async () => {
    if (!code.trim()) {
      setSubmitError('Write some code first.')
      return
    }
    setSubmitting(true)
    setSubmitError(null)
    setResult(null)
    try {
      const res = await submitProblem(problem.id, { code, language })
      setResult(res.data)
      setProblem((p) => ({ ...p, status: res.data.status, attempts_count: res.data.attempts_count, last_code: code }))
    } catch (e) {
      setSubmitError(errorMessage(e))
    } finally {
      setSubmitting(false)
    }
  }

  const handleMarkSolved = async () => {
    if (!window.confirm('Mark this problem as solved without an AI review?')) return
    setMarking(true)
    setSubmitError(null)
    try {
      const res = await markProblemSolved(problem.id)
      setProblem((p) => ({ ...p, status: res.data.status, solved_at: res.data.solved_at }))
    } catch (e) {
      setSubmitError(errorMessage(e))
    } finally {
      setMarking(false)
    }
  }

  if (loadError) {
    return (
      <div className="space-y-4">
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm">{loadError}</div>
        <Link to="/problems" className="text-blue-600 hover:underline text-sm">← Back to problems</Link>
      </div>
    )
  }
  if (!problem) return <div className="text-slate-400 animate-pulse">Loading problem…</div>

  return (
    <div className="space-y-4">
      <Link to="/problems" className="text-blue-600 hover:underline text-sm">← All problems</Link>

      <div className="grid lg:grid-cols-2 gap-6 items-start">
        {/* ── left: the question ─────────────────────────────────────────── */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
            <div className="flex items-start justify-between gap-3">
              <h1 className="text-2xl font-bold">{problem.title}</h1>
              <span className="flex items-center gap-1.5 text-sm text-slate-600 shrink-0 pt-1">
                <StatusIcon status={problem.status} />
                {STATUS_LABELS[problem.status] || 'Todo'}
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <DifficultyBadge difficulty={problem.difficulty} />
              <TopicChips topics={problem.topics} />
            </div>

            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
              {problem.acceptance_rate != null && <span>Acceptance {problem.acceptance_rate.toFixed(1)}%</span>}
              <span>Attempts: {problem.attempts_count}</span>
              {problem.url && (
                <a href={problem.url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
                  Open original ↗
                </a>
              )}
            </div>

            <Description text={problem.description} />
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-3">
            <h2 className="font-bold">🔗 Similar questions</h2>
            {similar.state === 'loading' && <p className="text-sm text-slate-400 animate-pulse">Finding similar questions…</p>}
            {similar.state === 'error' && <p className="text-sm text-slate-400">Couldn&apos;t load similar questions.</p>}
            {similar.state === 'ok' && similar.items.length === 0 && (
              <p className="text-sm text-slate-400">No similar questions found.</p>
            )}
            {similar.items.map((q) => (
              <div key={q.title} className="flex items-center justify-between gap-3 text-sm border-t border-slate-100 pt-3 first:border-0 first:pt-0">
                <div className="min-w-0">
                  {q.problem_id ? (
                    <Link to={`/problems/${q.problem_id}`} className="font-medium text-blue-600 hover:underline">
                      {q.title}
                    </Link>
                  ) : (
                    <a
                      href={`https://leetcode.com/problems/${q.title.toLowerCase().replace(/\s+/g, '-')}/`}
                      target="_blank"
                      rel="noreferrer"
                      className="font-medium text-blue-600 hover:underline"
                    >
                      {q.title} ↗
                    </a>
                  )}
                  <div className="text-xs text-slate-400">
                    Similarity {(q.similarity_score * 100).toFixed(0)}%
                  </div>
                </div>
                <DifficultyBadge difficulty={q.difficulty} />
              </div>
            ))}
          </div>
        </div>

        {/* ── right: editor + review ─────────────────────────────────────── */}
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <select
                className="border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white"
                aria-label="Language"
                value={language}
                onChange={(e) => onLanguageChange(e.target.value)}
              >
                {LANGUAGES.map((l) => (
                  <option key={l.value} value={l.value}>{l.label}</option>
                ))}
              </select>
              <div className="flex items-center gap-2">
                {problem.status !== 'solved' && (
                  <button
                    onClick={handleMarkSolved}
                    disabled={marking || submitting}
                    className="text-sm text-slate-600 border border-slate-300 px-3 py-2 rounded-lg hover:bg-slate-50 disabled:opacity-50"
                    title="For problems you solved elsewhere"
                  >
                    {marking ? 'Saving…' : 'I solved it'}
                  </button>
                )}
                <button
                  onClick={handleSubmit}
                  disabled={submitting || marking}
                  className="bg-blue-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50"
                >
                  {submitting ? 'Reviewing…' : 'Submit'}
                </button>
              </div>
            </div>

            <div className="border border-slate-300 rounded-lg overflow-hidden">
              <Editor
                height="420px"
                language={language}
                value={code}
                onChange={(val) => setCode(val ?? '')}
                theme="vs-dark"
                options={{ minimap: { enabled: false }, fontSize: 14, scrollBeyondLastLine: false, automaticLayout: true }}
              />
            </div>
          </div>

          <h2 className="font-bold text-lg">AI Review</h2>

          {submitError && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm">{submitError}</div>
          )}

          {submitting && (
            <div className="bg-slate-100 rounded-lg p-6 text-slate-400 text-center animate-pulse">
              Calling AI model…
            </div>
          )}

          {!result && !submitError && !submitting && (
            <div className="bg-slate-100 rounded-lg p-6 text-slate-400 text-center">
              Submit your solution to get feedback here
            </div>
          )}

          {result && (
            <div className="space-y-3">
              <Verdict result={result} />
              <ReviewPanel review={result.review} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Verdict({ result }) {
  if (result.newly_solved) {
    return (
      <div className="bg-green-50 border border-green-300 text-green-800 rounded-lg p-4 text-sm font-medium">
        🎉 Solved! The review found no bugs, so this problem is now marked as solved.
      </div>
    )
  }
  if (result.clean) {
    return (
      <div className="bg-green-50 border border-green-200 text-green-800 rounded-lg p-4 text-sm">
        No bugs found. This problem was already solved.
      </div>
    )
  }
  return (
    <div className="bg-amber-50 border border-amber-200 text-amber-800 rounded-lg p-4 text-sm">
      {result.status === 'solved'
        ? 'This submission has issues, but the problem stays marked as solved.'
        : 'Not solved yet. Fix the bugs below and submit again.'}
    </div>
  )
}

// Descriptions are plain text with `inline code` and section labels such as "Example 1:".
// Rendered as React text nodes (never as HTML), so any markup in the data is shown literally.
const SECTION_LABEL = /^(Example \d+:|Constraints:|Follow[- ]up:|Note:|Notes?:)/

function Description({ text }) {
  const lines = (text || '').split('\n')
  return (
    <div className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
      {lines.map((line, i) => {
        if (!line.trim()) return <div key={i} className="h-3" />
        const label = SECTION_LABEL.test(line.trim())
        return (
          <p key={i} className={label ? 'font-semibold text-slate-900 mt-2' : ''}>
            {line.split(/(`[^`]+`)/g).map((part, j) =>
              part.length > 2 && part.startsWith('`') && part.endsWith('`') ? (
                <code key={j} className="bg-slate-100 text-slate-800 rounded px-1 py-0.5 text-[0.85em]">
                  {part.slice(1, -1)}
                </code>
              ) : (
                <span key={j}>{part}</span>
              ),
            )}
          </p>
        )
      })}
    </div>
  )
}
