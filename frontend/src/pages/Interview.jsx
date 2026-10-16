import { useEffect, useRef, useState } from 'react'
import { startInterview, sendAnswer, getInterview, getScorecard, getInterviewTopics } from '../api'
import { useAuth } from '../auth/useAuth'

export default function Interview() {
  const { user } = useAuth()
  const STORAGE_KEY = `interview_session_id_${user.id}` // har user ka apna session
  const [topics, setTopics] = useState(['arrays'])
  const [topic, setTopic] = useState('arrays')
  const [sessionId, setSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [status, setStatus] = useState('idle') // idle | active | finished | expired
  const [turns, setTurns] = useState({ used: 0, max: 12 })
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [scorecard, setScorecard] = useState(null)
  const bottomRef = useRef(null)

  // Page reload ya server restart ke baad session DB se wapas aata hai
  useEffect(() => {
    getInterviewTopics().then((r) => setTopics(r.data.topics)).catch(() => {})
    const saved = localStorage.getItem(STORAGE_KEY)
    if (!saved) return
    getInterview(saved)
      .then((r) => {
        setSessionId(r.data.session_id)
        setMessages(r.data.history)
        setStatus(r.data.status)
        setTurns({ used: r.data.turns_used, max: r.data.max_turns })
        if (r.data.status === 'finished') {
          getScorecard(saved).then((sc) => setScorecard(sc.data)).catch(() => {})
        }
      })
      .catch(() => localStorage.removeItem(STORAGE_KEY))
  }, [STORAGE_KEY])

  const loadScorecard = (id) => getScorecard(id).then((r) => setScorecard(r.data)).catch(() => {})

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleStart = async () => {
    setLoading(true)
    setError(null)
    setScorecard(null)
    try {
      const r = await startInterview({ user_id: user.id, topic })
      localStorage.setItem(STORAGE_KEY, r.data.session_id)
      setSessionId(r.data.session_id)
      setMessages([{ role: 'assistant', content: r.data.reply }])
      setStatus(r.data.status)
      setTurns({ used: 0, max: r.data.max_turns })
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleSend = async () => {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setLoading(true)
    setError(null)
    setMessages((m) => [...m, { role: 'user', content: text }])
    try {
      const r = await sendAnswer(sessionId, { answer: text })
      setMessages((m) => [...m, { role: 'assistant', content: r.data.reply }])
      setStatus(r.data.status)
      setTurns({ used: r.data.turns_used, max: r.data.max_turns })
      if (r.data.status === 'finished') loadScorecard(sessionId)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleNew = () => {
    localStorage.removeItem(STORAGE_KEY)
    setSessionId(null)
    setMessages([])
    setStatus('idle')
    setScorecard(null)
    setError(null)
  }

  if (status === 'idle') {
    return (
      <div className="space-y-6 max-w-xl">
        <div>
          <h1 className="text-3xl font-bold">🎤 Mock Interview</h1>
          <p className="text-slate-500 mt-1">An AI interviewer asks questions, follows up, gives hints and scores you.</p>
        </div>
        <div>
          <label className="text-sm font-medium block mb-1">Preferred topic</label>
          <select
            className="w-full border border-slate-300 rounded-lg px-3 py-2"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
          >
            {topics.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
        <button
          onClick={handleStart}
          disabled={loading}
          className="bg-blue-600 text-white px-5 py-2 rounded-lg disabled:opacity-50"
        >
          {loading ? 'Starting…' : 'Start interview'}
        </button>
        {error && <p className="text-red-600 text-sm">{error}</p>}
      </div>
    )
  }

  return (
    <div className="space-y-4 max-w-3xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">🎤 Mock Interview</h1>
        <div className="text-sm text-slate-500">
          Turn {turns.used}/{turns.max} · <span className="font-medium">{status}</span>
          <button onClick={handleNew} className="ml-3 text-blue-600 underline">New interview</button>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-4 h-[420px] overflow-y-auto space-y-3">
        {messages.map((m, i) => (
          <div key={i} className={m.role === 'user' ? 'text-right' : 'text-left'}>
            <div
              className={`inline-block max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm ${
                m.role === 'user' ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-800'
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}
        {loading && <p className="text-slate-400 text-sm">Interviewer is thinking…</p>}
        <div ref={bottomRef} />
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      {status === 'active' ? (
        <div className="flex gap-2">
          <textarea
            className="flex-1 border border-slate-300 rounded-lg px-3 py-2 font-mono text-sm"
            rows={4}
            placeholder="Explain your approach, or paste your Python code…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="bg-blue-600 text-white px-4 rounded-lg disabled:opacity-50"
          >
            Send
          </button>
        </div>
      ) : (
        <p className="text-slate-500 text-sm">
          {status === 'expired' ? 'Turn limit reached, interview closed without a scorecard.' : 'Interview finished.'}
        </p>
      )}

      {scorecard && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-3">
          <h2 className="text-xl font-bold">Scorecard: {scorecard.total}/{scorecard.out_of}</h2>
          <div className="grid grid-cols-2 gap-3 text-sm">
            {['approach', 'complexity', 'edge_cases', 'communication'].map((k) => (
              <div key={k} className="bg-slate-50 rounded-lg p-3">
                <div className="text-slate-500 capitalize">{k.replace('_', ' ')}</div>
                <div className="text-lg font-semibold">{scorecard[k]}/5</div>
              </div>
            ))}
          </div>
          {scorecard.weak_patterns?.length > 0 && (
            <p className="text-sm">
              <span className="font-medium">Weak patterns:</span> {scorecard.weak_patterns.join(', ')}
            </p>
          )}
          {scorecard.summary && <p className="text-sm text-slate-600">{scorecard.summary}</p>}
        </div>
      )}
    </div>
  )
}
