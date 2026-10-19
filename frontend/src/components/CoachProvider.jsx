// One Coach for the whole app: a floating button (with an unread dot) + the chat panel.
// Pages can give the Coach context (ProblemPage: the problem + the code in the editor) through
// useCoach().registerContext(...), and open it with openCoach().
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useAuth } from '../auth/useAuth'
import { useLocation } from 'react-router-dom'
import { getCheckinToday, getStreak } from '../api'
import CoachWidget from './CoachWidget'
import { CoachContext } from './coachContext'

const seenKey = (userId, date) => `coach_seen:${userId}:${date}`

function readSeen(key) {
  try { return localStorage.getItem(key) === '1' } catch { return false }
}

export default function CoachProvider({ children }) {
  const { user } = useAuth()
  const { pathname } = useLocation()
  const [open, setOpen] = useState(false)
  const [streak, setStreak] = useState(0)
  const [ctx, setCtx] = useState(null)                      // { problem, getCode, onReply } from the current page
  const [attention, setAttention] = useState({ needs: false, unread: 0, date: null, seen: false })

  // Fetch the follow-up summary for the dot: on load, and again each time the panel closes.
  useEffect(() => {
    if (open || !user) return undefined
    let cancelled = false
    getCheckinToday()
      .then((res) => {
        if (cancelled) return
        const d = res.data
        setAttention({
          needs: d.needs_attention,
          unread: d.unread_notifications,
          date: d.date,
          seen: readSeen(seenKey(user.id, d.date)),
        })
      })
      .catch(() => { /* the dot is a nicety: stay quiet if the backend is unreachable */ })
    return () => { cancelled = true }
  }, [open, user])

  // Tiny streak badge on the floating button. Refreshed on load and every time the panel closes.
  useEffect(() => {
    if (open || !user) return undefined
    let cancelled = false
    getStreak()
      .then((res) => { if (!cancelled) setStreak(res.data.current_streak ?? 0) })
      .catch(() => { /* optional */ })
    return () => { cancelled = true }
  }, [open, user])

  const openCoach = useCallback(() => {
    setOpen(true)
    setAttention((a) => {
      if (user && a.date) {
        try { localStorage.setItem(seenKey(user.id, a.date), '1') } catch { /* ignore */ }
      }
      return { ...a, unread: 0, seen: true }
    })
  }, [user])
  const closeCoach = useCallback(() => setOpen(false), [])
  const registerContext = useCallback((next) => {
    setCtx(next)
    return () => setCtx(null)
  }, [])

  const value = useMemo(
    () => ({ open, openCoach, closeCoach, registerContext }),
    [open, openCoach, closeCoach, registerContext],
  )
  const showDot = attention.unread > 0 || (attention.needs && !attention.seen)

  return (
    <CoachContext.Provider value={value}>
      {children}
      {!open && pathname !== '/coach' && (
        <button
          type="button"
          onClick={openCoach}
          aria-label={showDot ? 'Open Coach chat (new follow-ups)' : 'Open Coach chat'}
          className="fixed bottom-4 right-4 z-30 w-14 h-14 rounded-full bg-blue-600 text-white text-2xl shadow-glow flex items-center justify-center hover:bg-blue-700 hover:scale-105 transition-transform"
        >
          <span aria-hidden="true">🤖</span>
          {showDot && (
            <span
              aria-hidden="true"
              className="absolute top-0 right-0 w-3.5 h-3.5 rounded-full bg-red-500 border-2 border-surface"
            />
          )}
          {streak > 0 && (
            <span
              aria-label={`${streak} day streak`}
              className="absolute -bottom-1 -left-1 text-[10px] font-bold bg-surface border border-line text-orange-500 rounded-full px-1.5 py-0.5"
            >
              🔥{streak}
            </span>
          )}
        </button>
      )}
      <CoachWidget
        open={open}
        onClose={closeCoach}
        problem={ctx?.problem}
        getCode={ctx?.getCode}
        onReply={ctx?.onReply}
      />
    </CoachContext.Provider>
  )
}
