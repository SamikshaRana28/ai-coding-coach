// Coach hub: Chat | Today & Plan | Interview Practice (the old "Mock Interview", now with rounds, voice and camera).
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import CoachChat from '../components/CoachChat'
import TodayCard from '../components/TodayCard'
import FocusCard from '../components/FocusCard'
import Interview from './Interview'

const TABS = [
  { id: 'chat', label: '💬 Chat' },
  { id: 'today', label: '🔥 Today & Plan' },
  { id: 'interview', label: '🎤 Interview Practice' },
]

export default function Coach() {
  const [params, setParams] = useSearchParams()
  const requested = params.get('tab')
  const tab = TABS.some((t) => t.id === requested) ? requested : 'chat'
  // The interview keeps its live state (camera, session) when you peek at another tab, so mount it on first visit only.
  const [interviewSeen, setInterviewSeen] = useState(tab === 'interview')
  const select = (id) => {
    if (id === 'interview') setInterviewSeen(true)
    setParams(id === 'chat' ? {} : { tab: id }, { replace: true })
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-3xl font-bold">🤖 Coach</h1>
        <p className="text-slate-500 mt-1">Chat with your coach, see today's tasks and streak, or practise a mock interview.</p>
      </div>

      <div role="tablist" aria-label="Coach sections" className="flex flex-wrap gap-2 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls={`panel-${t.id}`}
            type="button"
            onClick={() => select(t.id)}
            className={`px-4 py-2 text-sm rounded-t-lg border-b-2 -mb-px ${
              tab === t.id ? 'border-accent text-slate-900 font-semibold' : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" id="panel-chat" aria-labelledby="tab-chat" hidden={tab !== 'chat'}>
        <div className="card h-[calc(100vh-17rem)] min-h-[420px] flex flex-col overflow-hidden">
          <CoachChat active={tab === 'chat'} className="flex-1" />
        </div>
      </div>

      <div role="tabpanel" id="panel-today" aria-labelledby="tab-today" hidden={tab !== 'today'} className="space-y-4">
        {tab === 'today' && (
          <>
            <div className="grid md:grid-cols-3 gap-4">
              <div className="md:col-span-2"><TodayCard /></div>
              <FocusCard />
            </div>
            <Link to="/plan" className="inline-block text-sm text-blue-400 underline">Open the full 7-day plan →</Link>
          </>
        )}
      </div>

      <div role="tabpanel" id="panel-interview" aria-labelledby="tab-interview" hidden={tab !== 'interview'}>
        {interviewSeen && <Interview />}
      </div>
    </div>
  )
}
