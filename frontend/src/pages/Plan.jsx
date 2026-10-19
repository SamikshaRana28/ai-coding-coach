// Study plan page: 7-day board with checkboxes, progress, focus topics with reasons, regenerate,
// and the weekly review (proposal -> confirm / keep current plan).
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  getCurrentPlan, getStreak, getWeeklyReview, generatePlan, completeTask, skipTask, rescheduleTasks,
  startWeeklyReview, confirmWeeklyReview, discardWeeklyReview, errorMessage,
} from '../api'
import { PLAN_CHANGED_EVENT } from '../components/coachContext'
import { DifficultyBadge } from '../components/ProblemBits'
import { StreakBadge, WeekDots } from '../components/StreakBadge'

const TOPICS = ['arrays', 'dp', 'graphs', 'trees', 'strings', 'math', 'others']
const topicLabel = (t) => (t === 'dp' ? 'DP' : t.charAt(0).toUpperCase() + t.slice(1))
const shortDate = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })

// progress numbers recomputed locally after a tick, so the board updates without a reload
function withProgress(plan) {
  const tasks = plan.days.flatMap((d) => d.tasks)
  const done = tasks.filter((t) => t.status === 'done').length
  const skipped = tasks.filter((t) => t.status === 'skipped').length
  return {
    ...plan,
    progress: {
      done, skipped, total: tasks.length, pending: tasks.length - done - skipped,
      percent: tasks.length ? Math.round((100 * done) / tasks.length) : 0,
    },
  }
}

const withTask = (plan, task) => withProgress({
  ...plan,
  days: plan.days.map((d) => ({ ...d, tasks: d.tasks.map((t) => (t.id === task.id ? { ...t, ...task } : t)) })),
})

function GenerateForm({ hasPlan, busy, onSubmit, onCancel }) {
  const [goal, setGoal] = useState('')
  const [minutes, setMinutes] = useState('')
  const [focus, setFocus] = useState('')

  const submit = (e) => {
    e.preventDefault()
    onSubmit({
      goal: goal.trim() || undefined,
      minutes_per_day: minutes ? Number(minutes) : undefined,
      focus_topic: focus || undefined,
    })
  }
  const field = 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500'

  return (
    <form onSubmit={submit} className="bg-surface rounded-xl p-6 border border-slate-200 space-y-4">
      <h2 className="font-bold text-lg">{hasPlan ? 'Regenerate your plan' : 'Make your 7-day plan'}</h2>
      <p className="text-sm text-slate-500">
        The plan is built from your real stats: weak topics first, a few mixed problems and a short revision.
        {hasPlan && ' Your current plan will be archived.'}
      </p>
      <div className="grid md:grid-cols-3 gap-4">
        <label className="text-sm md:col-span-3">
          <span className="block text-slate-600 mb-1">Goal (optional)</span>
          <input value={goal} onChange={(e) => setGoal(e.target.value)} maxLength={200}
                 placeholder="e.g. interview in 4 weeks" className={field} />
        </label>
        <label className="text-sm">
          <span className="block text-slate-600 mb-1">Time per day</span>
          <select value={minutes} onChange={(e) => setMinutes(e.target.value)} className={field}>
            <option value="">Default (3 tasks a day)</option>
            <option value="30">30 min (2 tasks a day)</option>
            <option value="60">60 min</option>
            <option value="90">90 min</option>
          </select>
        </label>
        <label className="text-sm">
          <span className="block text-slate-600 mb-1">Focus on a topic (optional)</span>
          <select value={focus} onChange={(e) => setFocus(e.target.value)} className={field}>
            <option value="">Let the plan decide</option>
            {TOPICS.map((t) => <option key={t} value={t}>{topicLabel(t)}</option>)}
          </select>
        </label>
      </div>
      <div className="flex gap-3">
        <button type="submit" disabled={busy}
                className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1">
          {busy ? 'Building your plan…' : hasPlan ? 'Regenerate plan' : 'Generate plan'}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel} className="text-sm text-slate-500 hover:text-slate-800 px-3">Cancel</button>
        )}
      </div>
    </form>
  )
}

function TaskRow({ task, busy, onComplete, onSkip, past }) {
  const done = task.status === 'done'
  const title = task.problem_id ? (
    <Link to={`/problems/${task.problem_id}`}
          className={`hover:underline ${done ? 'line-through text-slate-400' : 'text-slate-800'}`}>{task.title}</Link>
  ) : (
    <span className={done ? 'line-through text-slate-400' : 'text-slate-800'}>{task.title}</span>
  )
  return (
    <li className="flex items-start gap-2 text-sm">
      <input type="checkbox" checked={done} disabled={done || busy} onChange={() => onComplete(task)}
             aria-label={`Mark done: ${task.title}`} className="mt-0.5 w-4 h-4 accent-green-600" />
      <div className="min-w-0 flex-1">
        <div className="break-words">{title}</div>
        <div className="flex flex-wrap items-center gap-2 mt-0.5">
          {task.difficulty && <DifficultyBadge difficulty={task.difficulty} />}
          {task.kind === 'revise' && <span className="text-xs text-purple-600">revision</span>}
          {task.kind === 'concept' && <span className="text-xs text-blue-600">concept</span>}
          {task.status === 'skipped' && <span className="text-xs text-slate-400">skipped</span>}
          {past && task.status === 'pending' && <span className="text-xs text-red-500">missed</span>}
          {task.status === 'pending' && (
            <button type="button" onClick={() => onSkip(task)} disabled={busy}
                    className="text-xs text-slate-400 hover:text-slate-700 underline focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded">
              skip
            </button>
          )}
        </div>
      </div>
    </li>
  )
}

function WeeklyReview({ proposal, busy, onConfirm, onDiscard }) {
  const { review, plan } = proposal
  const stat = (label, value) => (
    <div className="bg-slate-50 rounded-lg p-3 text-center">
      <div className="text-xl font-bold">{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  )
  return (
    <section aria-label="Weekly review" className="bg-surface rounded-xl p-6 border border-blue-200 space-y-4">
      <div>
        <h2 className="font-bold text-lg">📝 Weekly review</h2>
        <p className="text-sm text-slate-500">{shortDate(review.period.start)} – {shortDate(review.period.end)}</p>
      </div>
      <p className="text-sm text-slate-700">{review.narrative}</p>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {stat('Tasks done', `${review.tasks.done}/${review.tasks.total}`)}
        {stat('Problems solved', review.solved_total)}
        {stat('Active days', review.active_days)}
        {stat('Hints used', review.hints_used)}
      </div>
      <div className="grid md:grid-cols-2 gap-4 text-sm">
        <div>
          <h3 className="font-semibold text-green-700 mb-1">What improved</h3>
          <ul className="list-disc pl-5 space-y-1">{review.improved.map((t) => <li key={t}>{t}</li>)}</ul>
        </div>
        <div>
          <h3 className="font-semibold text-amber-700 mb-1">What did not</h3>
          {review.needs_work.length === 0
            ? <p className="text-slate-500">Nothing stood out. Nice.</p>
            : <ul className="list-disc pl-5 space-y-1">{review.needs_work.map((t) => <li key={t}>{t}</li>)}</ul>}
        </div>
      </div>

      <div className="border-t border-slate-100 pt-4 space-y-2">
        <h3 className="font-semibold">Next week (proposed): {shortDate(plan.week_start)} – {shortDate(plan.week_end)}</h3>
        <p className="text-sm text-slate-600">{plan.summary}</p>
        <ul className="text-xs text-slate-600 space-y-1">
          {plan.days.map((d) => (
            <li key={d.date}><span className="font-medium">{d.weekday}:</span> {d.tasks.map((t) => t.title).join(' · ')}</li>
          ))}
        </ul>
      </div>
      <div className="flex gap-3">
        <button type="button" onClick={onConfirm} disabled={busy}
                className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">
          Use this plan
        </button>
        <button type="button" onClick={onDiscard} disabled={busy}
                className="text-sm text-slate-600 border border-slate-300 px-4 py-2 rounded-lg hover:bg-slate-50 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">
          Keep my current plan
        </button>
      </div>
    </section>
  )
}

export default function Plan() {
  const [params] = useSearchParams()
  const wantReview = useRef(params.get('review') === '1')      // arrived from the Coach's "weekly review" button
  const [state, setState] = useState({ status: 'loading' })    // { status, plan, streak, proposal, message }
  const [reload, setReload] = useState(0)
  const [busy, setBusy] = useState(null)                       // 'generate' | 'review' | 'reschedule' | task id
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)

  useEffect(() => {
    let cancelled = false
    Promise.all([getCurrentPlan(), getStreak(), getWeeklyReview()])
      .then(([p, s, r]) => {
        if (cancelled) return
        const proposal = r.data.plan ? r.data : null
        setState({ status: 'ok', plan: p.data.plan, streak: s.data, proposal })
        // Opened with ?review=1 (the Coach's weekly-review button): start the review once.
        if (wantReview.current) {
          wantReview.current = false
          window.history.replaceState(null, '', '/plan')
          if (p.data.plan && !proposal) {
            startWeeklyReview()
              .then((res) => { if (!cancelled) setState((st) => ({ ...st, proposal: res.data })) })
              .catch((e) => { if (!cancelled) setError(errorMessage(e)) })
          }
        }
      })
      .catch((e) => { if (!cancelled) setState({ status: 'error', message: errorMessage(e) }) })
    return () => { cancelled = true }
  }, [reload])

  useEffect(() => {
    const onChange = () => setReload((n) => n + 1)
    window.addEventListener(PLAN_CHANGED_EVENT, onChange)
    return () => window.removeEventListener(PLAN_CHANGED_EVENT, onChange)
  }, [])

  const run = useCallback(async (key, fn) => {
    setBusy(key)
    setError(null)
    try {
      await fn()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(null)
    }
  }, [])

  const onGenerate = (body) => {
    if (state.plan && !window.confirm('This replaces your current plan (it is archived). Continue?')) return
    run('generate', async () => {
      await generatePlan(body)
      setShowForm(false)
      setReload((n) => n + 1)
    })
  }

  const tick = (task) => run(task.id, async () => {
    const res = await completeTask(task.id)
    setState((s) => ({ ...s, plan: withTask(s.plan, res.data.task), streak: res.data.streak }))
  })

  const skip = (task) => run(task.id, async () => {
    const res = await skipTask(task.id)
    setState((s) => ({ ...s, plan: withTask(s.plan, res.data.task) }))
  })

  const moveMissed = () => run('reschedule', async () => {
    await rescheduleTasks()
    setReload((n) => n + 1)
  })

  const startReview = useCallback(() => run('review', async () => {
    const res = await startWeeklyReview()
    setState((s) => ({ ...s, proposal: res.data }))
  }), [run])

  const confirmReview = () => run('review', async () => {
    await confirmWeeklyReview()
    setReload((n) => n + 1)
  })

  const discardReview = () => run('review', async () => {
    await discardWeeklyReview()
    setState((s) => ({ ...s, proposal: null }))
  })

  if (state.status === 'loading') return <p className="text-slate-400 animate-pulse">Loading your plan…</p>
  if (state.status === 'error') {
    return <div role="alert" className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm">Could not load your plan: {state.message}</div>
  }

  const { plan, streak, proposal } = state
  const missed = plan ? plan.days.filter((d) => d.is_past).flatMap((d) => d.tasks).filter((t) => t.status === 'pending').length : 0

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">📅 Study Plan</h1>
          <p className="text-slate-500 mt-1">A 7-day schedule built from your own progress</p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <StreakBadge streak={streak} />
          <WeekDots week={streak.week} />
        </div>
      </div>

      {error && <div role="alert" className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">{error}</div>}

      {!plan && (
        <GenerateForm hasPlan={false} busy={busy === 'generate'} onSubmit={onGenerate} />
      )}

      {proposal && (
        <WeeklyReview proposal={proposal} busy={busy === 'review'} onConfirm={confirmReview} onDiscard={discardReview} />
      )}

      {plan && (
        <>
          <section className="bg-surface rounded-xl p-6 border border-slate-200 space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm text-slate-700">{plan.summary}</p>
                {plan.goal && <p className="text-xs text-slate-500 mt-1">Goal: {plan.goal}</p>}
                <p className="text-xs text-slate-400 mt-1">
                  {shortDate(plan.week_start)} – {shortDate(plan.week_end)} ·{' '}
                  {plan.source === 'llm' ? 'arranged by the AI from your data' : 'built from your stats'}
                </p>
              </div>
              <div className="flex gap-2">
                {!proposal && (
                  <button type="button" onClick={startReview} disabled={busy === 'review'}
                          className="text-sm border border-slate-300 px-3 py-2 rounded-lg hover:bg-slate-50 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">
                    {busy === 'review' ? 'Preparing…' : 'Weekly review'}
                  </button>
                )}
                <button type="button" onClick={() => setShowForm((v) => !v)}
                        className="text-sm bg-blue-600 text-white px-3 py-2 rounded-lg hover:bg-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1">
                  Regenerate plan
                </button>
              </div>
            </div>
            <div>
              <div className="flex justify-between text-xs text-slate-500 mb-1">
                <span>Progress</span>
                <span>{plan.progress.done}/{plan.progress.total} tasks · {plan.progress.percent}%</span>
              </div>
              <div role="progressbar" aria-valuenow={plan.progress.percent} aria-valuemin={0} aria-valuemax={100}
                   aria-label="Plan progress" className="h-2 bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-green-500 transition-all" style={{ width: `${plan.progress.percent}%` }} />
              </div>
            </div>
            {missed > 0 && (
              <div className="flex flex-wrap items-center justify-between gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-sm">
                <span>{missed} unfinished task{missed === 1 ? '' : 's'} from earlier days.</span>
                <button type="button" onClick={moveMissed} disabled={busy === 'reschedule'}
                        className="text-blue-400 underline disabled:opacity-50">Move them to today</button>
              </div>
            )}
          </section>

          {showForm && (
            <GenerateForm hasPlan busy={busy === 'generate'} onSubmit={onGenerate} onCancel={() => setShowForm(false)} />
          )}

          <section aria-label="Focus topics" className="space-y-2">
            <h2 className="font-bold text-lg">Focus topics</h2>
            <div className="grid md:grid-cols-3 gap-4">
              {plan.focus_topics.map((f) => (
                <div key={f.topic} className="bg-surface rounded-xl p-4 border border-slate-200 space-y-2">
                  <div className="font-semibold">{topicLabel(f.topic)}</div>
                  <p className="text-sm text-slate-600">{f.reason}</p>
                  <div className="flex flex-wrap gap-1">
                    {f.patterns.map((p) => (
                      <span key={p} className="px-2 py-0.5 rounded-full text-xs bg-blue-50 text-blue-400 border border-blue-100">{p}</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section aria-label="7-day board" className="space-y-2">
            <h2 className="font-bold text-lg">This week</h2>
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7 gap-3">
              {plan.days.map((d) => (
                <div key={d.date}
                     className={`bg-surface rounded-xl p-3 border space-y-3 ${d.is_today ? 'border-blue-500 ring-2 ring-blue-200' : 'border-slate-200'}`}>
                  <div className="flex items-center justify-between">
                    <div className="font-semibold text-sm">{d.weekday} <span className="text-slate-400 font-normal">{shortDate(d.date)}</span></div>
                    {d.is_today && <span className="text-[10px] uppercase tracking-wide bg-blue-600 text-white rounded-full px-2 py-0.5">Today</span>}
                  </div>
                  {d.tasks.length === 0
                    ? <p className="text-xs text-slate-400">Rest day</p>
                    : (
                      <ul className="space-y-3">
                        {d.tasks.map((t) => (
                          <TaskRow key={t.id} task={t} busy={busy === t.id} past={d.is_past}
                                   onComplete={tick} onSkip={skip} />
                        ))}
                      </ul>
                    )}
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  )
}
