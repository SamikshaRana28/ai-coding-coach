// Small floating chat panel for the Coach (backend: POST /coach/chat, GET/DELETE /coach/history).
// Opened from the Problem page ("Ask Coach about this problem"); every message is sent together with
// that problem's id and the code currently in the editor, so the Coach knows what the student sees.
// The conversation itself lives on the server (/coach/history), so it survives closing the panel and
// leaving the page. A fuller Coach page / site-wide widget can reuse this component later.
import { useEffect, useRef, useState } from 'react'
import { coachChat, getCoachHistory, clearCoachHistory, errorMessage } from '../api'

const MAX_MESSAGE_CHARS = 2000   // keep in sync with coach_router.MAX_MESSAGE_CHARS
const MAX_CODE_CHARS = 8000      // keep in sync with coach_router.MAX_CODE_CHARS

function friendlyError(e) {
  // no e.response = the request never got an answer (server down / asleep / offline)
  if (!e?.response) return 'Could not reach the server. Please check your connection and try again.'
  return errorMessage(e)
}

export default function CoachWidget({ open, onClose, problem, getCode, onReply }) {
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
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setSending(false)
    }
  }

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
      className="fixed bottom-4 right-4 z-40 w-[min(26rem,calc(100vw-2rem))] h-[32rem] max-h-[80vh] bg-white border border-slate-200 rounded-xl shadow-xl flex flex-col"
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
        {historyLoading && <p className="text-slate-400 animate-pulse">Loading your conversation…</p>}
        {!historyLoading && messages.length === 0 && (
          <p className="text-slate-500">
            Ask me anything about this problem. I&apos;ll guide you with questions and hints, not hand you the
            full solution.
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
          placeholder="Ask about this problem…"
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
