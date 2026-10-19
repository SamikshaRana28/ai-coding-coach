import { useState } from 'react'
import { extractResume } from '../api'
import { friendlyError } from '../components/ui'
import { ROUNDS } from './rounds'
import { speechSupport } from './useSpeech'

export default function RoundSetup({ topics, onStart, loading, error }) {
  const support = speechSupport()
  const [round, setRound] = useState('dsa')
  const [topic, setTopic] = useState('arrays')
  const [resume, setResume] = useState(null)               // { name, text }
  const [resumeError, setResumeError] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [voice, setVoice] = useState(support.tts)
  const [camera, setCamera] = useState(false)

  const needsResume = round === 'resume'
  const usesResume = round === 'resume' || round === 'mixed'
  const canStart = !loading && !uploading && (!needsResume || resume)

  const onFile = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setResumeError(null)
    setUploading(true)
    try {
      const res = await extractResume(file)
      setResume({ name: file.name, text: res.data.resume_text })
    } catch (err) {
      setResume(null)
      setResumeError(friendlyError(err))
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <fieldset>
        <legend className="text-sm font-medium mb-2">Choose a round</legend>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3" role="radiogroup">
          {ROUNDS.map((r) => (
            <label
              key={r.id}
              className={`card p-4 cursor-pointer block focus-within:outline focus-within:outline-2 focus-within:outline-accent ${
                round === r.id ? 'border-accent bg-elevated' : 'hover:border-slate-300'
              }`}
            >
              <input type="radio" name="round" value={r.id} checked={round === r.id} onChange={() => setRound(r.id)} className="sr-only" />
              <div className="text-2xl" aria-hidden="true">{r.icon}</div>
              <div className="font-semibold mt-1">{r.title}</div>
              <div className="text-xs text-slate-500 mt-1">{r.blurb}</div>
            </label>
          ))}
        </div>
      </fieldset>

      {(round === 'dsa' || round === 'mixed') && (
        <div>
          <label htmlFor="iv-topic" className="text-sm font-medium block mb-1">Preferred DSA topic</label>
          <select id="iv-topic" className="w-full sm:w-64 border border-slate-300 rounded-lg px-3 py-2" value={topic} onChange={(e) => setTopic(e.target.value)}>
            {topics.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
      )}

      {usesResume && (
        <div className="card p-4 space-y-2">
          <div className="text-sm font-medium">
            Resume (PDF){needsResume ? '' : ' · optional for Mixed'}
          </div>
          <p className="text-xs text-slate-500">
            Text is extracted on the server and used only for this interview. It is deleted when the interview ends.
          </p>
          {resume ? (
            <div className="flex items-center gap-3 text-sm">
              <span>📄 {resume.name} <span className="text-slate-500">({resume.text.length} characters read)</span></span>
              <button type="button" className="text-red-600 underline" onClick={() => setResume(null)}>Remove</button>
            </div>
          ) : (
            <input type="file" accept="application/pdf,.pdf" onChange={onFile} disabled={uploading} aria-label="Upload resume PDF" className="text-sm" />
          )}
          {uploading && <p className="text-xs text-slate-500 animate-pulse">Reading your resume…</p>}
          {resumeError && <p role="alert" className="text-xs text-red-600">{resumeError}</p>}
        </div>
      )}

      <div className="card p-4 space-y-3">
        <div className="text-sm font-medium">Practice options</div>
        <label className="flex items-start gap-3 text-sm">
          <input type="checkbox" className="mt-1 accent-green-600" checked={voice} disabled={!support.tts} onChange={(e) => setVoice(e.target.checked)} />
          <span>
            Interviewer speaks aloud, and I can answer with my voice
            {!support.stt && <span className="block text-xs text-amber-700">Voice input is not supported in this browser (use Chrome or Edge). You can still type.</span>}
          </span>
        </label>
        <label className="flex items-start gap-3 text-sm">
          <input type="checkbox" className="mt-1 accent-green-600" checked={camera} onChange={(e) => setCamera(e.target.checked)} />
          <span>
            Camera: eye contact and body-language feedback
            <span className="block text-xs text-slate-500">Runs in your browser. Video is never uploaded. You will see a consent screen first.</span>
          </span>
        </label>
      </div>

      {error && <p role="alert" className="text-red-600 text-sm">{error}</p>}
      <button
        type="button"
        disabled={!canStart}
        onClick={() => onStart({ round, topic, resumeText: usesResume ? resume?.text : undefined, voice, camera })}
        className="bg-blue-600 text-white px-6 py-2.5 rounded-lg hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? 'Starting…' : 'Start interview'}
      </button>
      {needsResume && !resume && <p className="text-xs text-slate-500">Upload your resume PDF to start the resume round.</p>}
    </div>
  )
}
