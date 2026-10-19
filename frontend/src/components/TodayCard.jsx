// Dashboard card: today's tasks (tick them off), the streak flame and a 7-dot activity row.
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getTodayTasks, getStreak, completeTask, errorMessage } from '../api'
import { PLAN_CHANGED_EVENT } from './coachContext'
import { DifficultyBadge } from './ProblemBits'
import { StreakBadge, WeekDots } from './StreakBadge'

export default function TodayCard() {
  const [data, setData] = useState({ status: 'loading' })
  const [reload, setReload] = useState(0)
  const [busyId, setBusyId] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([getTodayTasks(), getStreak()])
      .then(([t, s]) => { if (!cancelled) setData({ status: 'ok', today: t.data, streak: s.data }) })
      .catch((e) => { if (!cancelled) setData({ status: 'error', message: errorMessage(e) }) })
    return () => { cancelled = true }
  }, [reload])

  // The Coach (or another tab of the app) may change the plan: reload when it says so.
  useEffect(() => {
    const onChange = () => setReload((n) => n + 1)
    window.addEventListener(PLAN_CHANGED_EVENT, onChange)
    return () => window.removeEventListener(PLAN_CHANGED_EVENT, onChange)
  }, [])

  const tick = async (task) => {
    setBusyId(task.id)
    setError(null)
    try {
      const res = await completeTask(task.id)
      setData((d) => ({
        ...d,
        today: {
          ...d.today,
          tasks: d.today.tasks.map((t) => (t.id === task.id ? res.data.task : t)),
          progress: {
            ...d.today.progress,
            done: d.today.progress.done + (res.data.changed ? 1 : 0),
            pending: Math.max(0, d.today.progress.pending - (res.data.changed ? 1 : 0)),
          },
        },
        streak: res.data.streak,
      }))
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusyId(null)
    }
  }

  const card = 'bg-white rounded-xl p-6 border border-slate-200'
  if (data.status === 'loading') return <div className={`${card} animate-pulse text-slate-400`}>Loading today…</div>
  if (data.status === 'error') return <div className={`${card} text-red-600 text-sm`}>Could not load today&apos;s tasks: {data.message}</div>

  const { today, streak } = data
  return (
    <section className={`${card} space-y-4`} aria-label="Today">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="font-bold text-lg">Today</h2>
          <p className="text-sm text-slate-500">
            {today.has_plan
              ? `${today.progress.done} of ${today.progress.total} tasks done`
              : 'No study plan yet'}
          </p>
        </div>
        <StreakBadge streak={streak} />
      </div>

      {!today.has_plan && (
        <p className="text-sm">
          <Link to="/plan" className="text-blue-600 underline">Make your 7-day plan</Link> and your daily tasks show up here.
        </p>
      )}
      {today.has_plan && today.tasks.length === 0 && (
        <p className="text-sm text-slate-500">Nothing is scheduled for today. <Link to="/plan" className="text-blue-600 underline">See your plan</Link>.</p>
      )}

      <ul className="space-y-2">
        {today.tasks.map((t) => (
          <li key={t.id} className="flex items-center gap-3 text-sm">
            <input
              type="checkbox"
              checked={t.status === 'done'}
              disabled={t.status === 'done' || busyId === t.id}
              onChange={() => tick(t)}
              aria-label={`Mark done: ${t.title}`}
              className="w-4 h-4 accent-green-600"
            />
            {t.problem_id ? (
              <Link to={`/problems/${t.problem_id}`}
                    className={`hover:underline ${t.status === 'done' ? 'line-through text-slate-400' : 'text-slate-800'}`}>
                {t.title}
              </Link>
            ) : (
              <span className={t.status === 'done' ? 'line-through text-slate-400' : 'text-slate-800'}>{t.title}</span>
            )}
            {t.difficulty && <DifficultyBadge difficulty={t.difficulty} />}
            {t.status === 'skipped' && <span className="text-xs text-slate-400">skipped</span>}
          </li>
        ))}
      </ul>
      {error && <p role="alert" className="text-xs text-red-600">{error}</p>}

      <div className="flex items-center justify-between pt-2 border-t border-slate-100">
        <WeekDots week={streak.week} />
        <Link to="/plan" className="text-sm text-blue-600 hover:underline">Full plan →</Link>
      </div>
    </section>
  )
}
