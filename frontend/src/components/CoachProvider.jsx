// One Coach for the whole app: a floating button (with an unread dot) + the chat panel.
// Pages can give the Coach context (ProblemPage: the problem + the code in the editor) through
// useCoach().registerContext(...), and open it with openCoach().
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useAuth } from '../auth/useAuth'
import { getCheckinToday } from '../api'
import CoachWidget from './CoachWidget'
import { CoachContext } from './coachContext'

const seenKey = (userId, date) => `coach_seen:${userId}:${date}`

function readSeen(key) {
  try { return localStorage.getItem(key) === '1' } catch { return false }
}

export default function CoachProvider({ children }) {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
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
      {!open && (
        <button
          type="button"
          onClick={openCoach}
          aria-label={showDot ? 'Open Coach chat (new follow-ups)' : 'Open Coach chat'}
          className="fixed bottom-4 right-4 z-30 bg-blue-600 text-white rounded-full shadow-lg px-5 py-3 text-sm font-medium hover:bg-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
        >
          🤖 Coach
          {showDot && (
            <span
              aria-hidden="true"
              className="absolute -top-1 -right-1 w-3.5 h-3.5 rounded-full bg-red-500 border-2 border-white"
            />
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
