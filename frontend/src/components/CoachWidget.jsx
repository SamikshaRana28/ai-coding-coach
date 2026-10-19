// Small floating chat panel for the Coach (backend: POST /coach/chat, GET/DELETE /coach/history).
// Opened from the Problem page ("Ask Coach about this problem"); every message is sent together with
// that problem's id and the code currently in the editor, so the Coach knows what the student sees.
// The conversation itself lives on the server (/coach/history), so it survives closing the panel and
// leaving the page. A fuller Coach page / site-wide widget can reuse this component later.
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  coachChat, getCoachHistory, clearCoachHistory, getCheckinToday, saveCheckin, getNotifications,
  markNotificationsRead, rescheduleTasks, generatePlan, errorMessage,
} from '../api'
import { PLAN_TOOLS, PLAN_CHANGED_EVENT } from './coachContext'

const MAX_MESSAGE_CHARS = 2000   // keep in sync with coach_router.MAX_MESSAGE_CHARS
const MAX_CODE_CHARS = 8000      // keep in sync with coach_router.MAX_CODE_CHARS

function friendlyError(e) {
  // no e.response = the request never got an answer (server down / asleep / offline)
  if (!e?.response) return 'Could not reach the server. Please check your connection and try again.'
  return errorMessage(e)
}

const MOODS = [
  { value: 1, emoji: '😞', label: 'Rough' },
  { value: 2, emoji: '😕', label: 'Meh' },
  { value: 3, emoji: '😐', label: 'Okay' },
  { value: 4, emoji: '🙂', label: 'Good' },
  { value: 5, emoji: '😄', label: 'Great' },
]

// "How was your day?" (shown in the evening until it is answered once a day)
function CheckinForm({ questions, onSaved }) {
  const [mood, setMood] = useState(null)
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const save = async (e) => {
    e.preventDefault()
    if (mood === null && !note.trim()) return
    setSaving(true)
    setError(null)
    try {
      const res = await saveCheckin({ mood: mood ?? undefined, note: note.trim() || undefined })
      onSaved(res.data)
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={save} className="space-y-2">
      {questions.map((q) => <p key={q} className="font-medium">{q}</p>)}
      <div className="flex gap-1" role="radiogroup" aria-label="Mood">
        {MOODS.map((m) => (
          <button
            key={m.value}
            type="button"
            role="radio"
            aria-checked={mood === m.value}
            aria-label={`${m.value} of 5, ${m.label}`}
            onClick={() => setMood(m.value)}
            className={`flex-1 rounded-lg border py-1 text-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
              mood === m.value ? 'border-blue-500 bg-blue-100' : 'border-slate-200 bg-white hover:bg-slate-50'
            }`}
          >
            {m.emoji}
          </button>
        ))}
      </div>
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        maxLength={500}
        rows={2}
        placeholder="Did you follow the schedule? Anything on your mind? (optional)"
        aria-label="Check-in note"
        className="w-full border border-slate-300 rounded-lg px-2 py-1 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
      />
      {error && <p role="alert" className="text-xs text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={saving || (mood === null && !note.trim())}
        className="bg-blue-600 text-white px-3 py-1.5 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
      >
        {saving ? 'Saving…' : 'Save check-in'}
      </button>
    </form>
  )
}

export default function CoachWidget({ open, onClose, problem, getCode, onReply }) {
  const navigate = useNavigate()
  const [followups, setFollowups] = useState(null)        // GET /coach/checkin/today
  const [unreadNotes, setUnreadNotes] = useState([])      // notifications created by the cron while away
  const [checkinReply, setCheckinReply] = useState(null)  // answer after saving the check-in
  const [actionBusy, setActionBusy] = useState(null)
  const [actionNote, setActionNote] = useState(null)
  const [messages, setMessages] = useState([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)
  const loadedRef = useRef(false)
  const inputRef = useRef(null)
  const listRef = useRef(null)

  // Load the saved conversation the first time the panel opens.
  useEffect(() => {
    if (!open || loadedRef.current) return
    loadedRef.current = true
    getCoachHistory()
      .then((res) => setMessages(res.data.messages || []))
      .catch((e) => setError(friendlyError(e)))
      .finally(() => setHistoryLoading(false))
  }, [open])

  // Follow-ups (Part 6): what the Coach has to say today, built from the student's real data.
  const refreshFollowups = () =>
    getCheckinToday().then((res) => setFollowups(res.data)).catch(() => { /* chat still works */ })

  useEffect(() => {
    if (!open) return undefined
    let cancelled = false
    Promise.all([getCheckinToday(), getNotifications(5)])
      .then(([checkin, notes]) => {
        if (cancelled) return
        setFollowups(checkin.data)
        setUnreadNotes(notes.data.items.filter((n) => !n.read))
        if (notes.data.unread > 0) markNotificationsRead().catch(() => {})
      })
      .catch(() => { /* chat still works without follow-ups */ })
    return () => { cancelled = true }
  }, [open])

  // Focus the input when the panel opens.
  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  // Keep the newest message in view.
  useEffect(() => {
    const el = listRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, sending, open])

  if (!open) return null

  const send = async (e) => {
    e.preventDefault()
    const text = input.trim()
    if (!text || sending) return
    setMessages((prev) => [...prev, { id: `local-${Date.now()}`, role: 'user', content: text }])
    setInput('')
    setSending(true)
    setError(null)
    try {
      const code = (getCode?.() || '').slice(0, MAX_CODE_CHARS)
      const res = await coachChat({
        message: text,
        problem_id: problem?.id,
        code: code.trim() ? code : undefined,
      })
      setMessages((prev) => [
        ...prev,
        { id: `reply-${Date.now()}`, role: 'assistant', content: res.data.reply, tools_used: res.data.tools_used },
      ])
      onReply?.(res.data)
      if (res.data.tools_used?.some((t) => PLAN_TOOLS.includes(t))) {
        window.dispatchEvent(new Event(PLAN_CHANGED_EVENT))       // Plan page / Today card reload
        refreshFollowups()
      }
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setSending(false)
    }
  }

  const runAction = async (id) => {
    setActionBusy(id)
    setError(null)
    try {
      if (id === 'generate_plan') {
        onClose()
        navigate('/plan')
      } else if (id === 'weekly_review') {
        onClose()
        navigate('/plan?review=1')
      } else if (id === 'reschedule') {
        const res = await rescheduleTasks()
        setActionNote(`Moved ${res.data.moved} task${res.data.moved === 1 ? '' : 's'} to today.`)
        window.dispatchEvent(new Event(PLAN_CHANGED_EVENT))
        await refreshFollowups()
      } else if (id === 'lighten') {
        if (!window.confirm('Replace your current plan with a lighter one (2 short tasks a day)?')) return
        await generatePlan({ minutes_per_day: 30 })
        window.dispatchEvent(new Event(PLAN_CHANGED_EVENT))
        onClose()
        navigate('/plan')
      }
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setActionBusy(null)
    }
  }

  const actionButtons = (actions) => (
    <div className="flex flex-wrap gap-2 mt-2">
      {actions.map((a) => (
        <button
          key={a.id}
          type="button"
          disabled={actionBusy !== null}
          onClick={() => runAction(a.id)}
          className="bg-blue-600 text-white px-3 py-1 rounded-lg text-xs hover:bg-blue-700 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        >
          {actionBusy === a.id ? 'Working…' : a.label}
        </button>
      ))}
    </div>
  )

  const clearChat = async () => {
    if (!window.confirm('Delete your whole conversation with the Coach?')) return
    try {
      await clearCoachHistory()
      setMessages([])
      setError(null)
    } catch (err) {
      setError(friendlyError(err))
    }
  }

  return (
    <div
      role="dialog"
      aria-label="Coach chat"
      onKeyDown={(e) => { if (e.key === 'Escape') onClose() }}
      className="fixed bottom-4 right-4 z-40 w-[min(26rem,calc(100vw-2rem))] h-[36rem] max-h-[85vh] bg-white border border-slate-200 rounded-xl shadow-xl flex flex-col"
    >
      <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-slate-200">
        <div className="min-w-0">
          <div className="font-bold text-sm">🤖 Coach</div>
          {problem && (
            <div className="text-xs text-slate-500 truncate" title={problem.title}>
              About: {problem.title}
            </div>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {messages.length > 0 && (
            <button
              type="button"
              onClick={clearChat}
              className="text-xs text-slate-500 hover:text-red-600 px-2 py-1 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              Clear
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close Coach chat"
            className="text-slate-500 hover:text-slate-800 px-2 py-1 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            ✕
          </button>
        </div>
      </div>

      <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3 text-sm" aria-live="polite">
        {(followups?.messages?.length > 0 || unreadNotes.length > 0 || followups?.ask_checkin || checkinReply || actionNote) && (
          <section aria-label="Coach follow-ups" className="space-y-2 border border-blue-200 bg-blue-50 rounded-lg p-3">
            {unreadNotes.map((n) => (
              <p key={n.id} className="text-slate-800">🔔 {n.message}</p>
            ))}
            {followups?.messages?.map((m) => (
              <div key={m.kind} className="text-slate-800">
                <p>{m.text}</p>
                {m.actions.length > 0 && actionButtons(m.actions)}
              </div>
            ))}
            {actionNote && <p className="text-green-700 text-xs">{actionNote}</p>}
            {followups?.ask_checkin && !checkinReply && (
              <CheckinForm
                questions={followups.questions}
                onSaved={(data) => { setCheckinReply(data); refreshFollowups() }}
              />
            )}
            {checkinReply && (
              <div className="text-slate-800">
                <p>{checkinReply.reply}</p>
                {checkinReply.actions.length > 0 && actionButtons(checkinReply.actions)}
              </div>
            )}
          </section>
        )}
        {historyLoading && <p className="text-slate-400 animate-pulse">Loading your conversation…</p>}
        {!historyLoading && messages.length === 0 && (
          <p className="text-slate-500">
            {problem
              ? "Ask me anything about this problem. I'll guide you with questions and hints, not hand you the full solution."
              : "Ask me what to practise next, about your plan, today's tasks or any interview topic."}
          </p>
        )}
        {messages.map((m) => (
          <div key={m.id} className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 whitespace-pre-wrap break-words ${
                m.role === 'user' ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-800'
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}
        {sending && <p className="text-slate-400 animate-pulse">Coach is thinking…</p>}
        {error && (
          <div role="alert" className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-2 text-xs">
            {error}
          </div>
        )}
      </div>

      <form onSubmit={send} className="border-t border-slate-200 p-3 flex gap-2">
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          maxLength={MAX_MESSAGE_CHARS}
          placeholder={problem ? 'Ask about this problem…' : 'Ask the Coach…'}
          aria-label="Message to the Coach"
          className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1"
        >
          Send
        </button>
      </form>
    </div>
  )
}
