// The live interview screen: interviewer panel (animated circle + captions), your camera tile, live transcript,
// optional Monaco editor (DSA), and the answer box with a mic button.
import { useEffect, useRef, useState } from 'react'
import Editor from '@monaco-editor/react'
import { useSpeechRecognition, useSpeechSynthesis } from './useSpeech'
import { needsEditor, ROUNDS } from './rounds'

const MAX_ANSWER_CHARS = 8000          // keep in sync with interview_router.AnswerRequest
const STARTER = '# Write your solution here (Python)\n'

export default function InterviewRoom({
  round, messages, status, turns, loading, error, restored,
  onSend, onEnd,
  voiceOut, onToggleVoice,
  cameraOn, camera, onToggleCamera, videoRef, speechStatsRef,
}) {
  const [input, setInput] = useState('')
  const [code, setCode] = useState(STARTER)
  const [showEditor, setShowEditor] = useState(true)
  const bottomRef = useRef(null)
  const active = status === 'active'

  const tts = useSpeechSynthesis()
  const stt = useSpeechRecognition({
    onFinal: (t) => setInput((prev) => (prev ? `${prev} ${t}` : t)),
  })
  const { getStats } = stt
  useEffect(() => {
    if (speechStatsRef) speechStatsRef.current = getStats
  }, [speechStatsRef, getStats])

  // Read each NEW interviewer message aloud (not the old ones when a session is restored).
  const last = [...messages].reverse().find((m) => m.role === 'assistant')
  const lastKey = last ? `${messages.length}:${last.content.length}` : null
  const spokenRef = useRef(restored ? lastKey : null)
  const { speak, cancel: cancelSpeech } = tts
  const stopListening = stt.stop
  useEffect(() => {
    if (!voiceOut) { cancelSpeech(); return }
    if (!last || lastKey === spokenRef.current) return
    spokenRef.current = lastKey
    stopListening()                                   // do not listen to our own interviewer
    speak(last.content)
  }, [lastKey, voiceOut, last, speak, cancelSpeech, stopListening])

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, loading])
  useEffect(() => { if (!active) { stt.stop(); tts.cancel() } }, [active]) // eslint-disable-line react-hooks/exhaustive-deps

  const submit = (text) => {
    const t = text.trim()
    if (!t || loading || !active) return
    stt.stop()
    tts.cancel()
    onSend(t.slice(0, MAX_ANSWER_CHARS))
    setInput('')
  }
  const sendAnswer = () => submit(input)
  const sendWithCode = () => {
    const withCode = `${input.trim() ? `${input.trim()}\n\n` : ''}My code:\n\`\`\`python\n${code}\n\`\`\``
    submit(withCode)
  }

  const toggleMic = () => {
    if (stt.listening) stt.stop()
    else { tts.cancel(); stt.start() }
  }

  const roundMeta = ROUNDS.find((r) => r.id === round)
  const editorOn = needsEditor(round)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xl font-bold">{roundMeta?.icon} {roundMeta?.title} interview</h2>
        <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
          <span>Turn {turns.used}/{turns.max} · <span className="font-medium text-slate-700">{status}</span></span>
          {tts.supported && (
            <button type="button" onClick={onToggleVoice} aria-pressed={voiceOut}
              className="border border-line rounded-full px-3 py-1 text-xs hover:bg-elevated">
              {voiceOut ? '🔊 Voice on' : '🔇 Voice off'}
            </button>
          )}
          <button type="button" onClick={onToggleCamera} aria-pressed={cameraOn}
            className="border border-line rounded-full px-3 py-1 text-xs hover:bg-elevated">
            {cameraOn ? '📷 Camera on' : '📷 Camera off'}
          </button>
        </div>
      </div>

      <div className="grid lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3 space-y-4 min-w-0">
          {/* Interviewer */}
          <section className="card p-5 flex items-start gap-4" aria-label="Interviewer">
            <div className="relative shrink-0 w-16 h-16" aria-hidden="true">
              <div className={`absolute inset-0 rounded-full bg-accent/30 ${tts.speaking ? 'animate-ping' : ''}`} />
              <div className={`relative w-16 h-16 rounded-full bg-gradient-to-br from-accent to-cyan2 flex items-center justify-center text-2xl transition-transform ${tts.speaking ? 'scale-110' : ''}`}>
                🧑‍💼
              </div>
            </div>
            <div className="min-w-0 flex-1" aria-live="polite">
              <div className="text-xs text-slate-500 mb-1">
                Interviewer {loading ? '· thinking…' : tts.speaking ? '· speaking…' : ''}
              </div>
              <p className="text-slate-800 whitespace-pre-wrap break-words">
                {last ? last.content : 'Getting ready…'}
              </p>
              {tts.speaking && (
                <button type="button" onClick={tts.cancel} className="text-xs text-slate-500 underline mt-2">Stop speaking</button>
              )}
            </div>
          </section>

          {/* Editor (DSA / Mixed) */}
          {editorOn && active && (
            <section className="card overflow-hidden" aria-label="Code editor">
              <div className="flex items-center justify-between px-4 py-2 border-b border-line text-sm">
                <span className="font-medium">Code (Python)</span>
                <button type="button" className="text-xs text-slate-500 underline" onClick={() => setShowEditor((v) => !v)}>
                  {showEditor ? 'Hide' : 'Show'}
                </button>
              </div>
              {showEditor && (
                <Editor height="260px" language="python" theme="vs-dark" value={code}
                  onChange={(v) => setCode(v ?? '')} options={{ minimap: { enabled: false }, fontSize: 14, scrollBeyondLastLine: false }} />
              )}
            </section>
          )}
        </div>

        <div className="lg:col-span-2 space-y-4 min-w-0">
          {/* Your camera */}
          <section className="card p-3" aria-label="Your camera">
            <div className="relative aspect-video rounded-lg overflow-hidden bg-canvas flex items-center justify-center">
              <video ref={videoRef} muted playsInline className={`w-full h-full object-cover -scale-x-100 ${cameraOn && camera.state === 'running' ? '' : 'hidden'}`} />
              {!(cameraOn && camera.state === 'running') && (
                <div className="text-center text-sm text-slate-500 px-4">
                  {!cameraOn && 'Camera is off. Answer with voice or text.'}
                  {cameraOn && camera.state === 'loading' && 'Starting camera and loading tracking models…'}
                  {cameraOn && camera.state === 'error' && 'Camera unavailable.'}
                </div>
              )}
            </div>
            <p className="text-[11px] text-slate-400 mt-2">🔒 Video stays on your device. Only summary numbers are saved.</p>
            {camera.error && <p role="alert" className="text-xs text-amber-700 mt-1">{camera.error}</p>}
          </section>

          {/* Live transcript */}
          <section className="card p-3" aria-label="Transcript">
            <h3 className="text-xs font-medium text-slate-500 mb-2">Live transcript</h3>
            <div className="max-h-64 overflow-y-auto space-y-2 text-sm pr-1">
              {messages.map((m, i) => (
                <div key={i} className={m.role === 'user' ? 'text-right' : 'text-left'}>
                  <div className={`inline-block max-w-[92%] whitespace-pre-wrap break-words rounded-lg px-3 py-1.5 ${
                    m.role === 'user' ? 'bg-blue-600 text-white' : 'bg-elevated text-slate-800'}`}>
                    {m.content}
                  </div>
                </div>
              ))}
              {loading && <p className="text-slate-400 text-xs animate-pulse">Interviewer is thinking…</p>}
              <div ref={bottomRef} />
            </div>
          </section>
        </div>
      </div>

      {error && <p role="alert" className="text-red-600 text-sm">{error}</p>}

      {active ? (
        <section className="card p-3 space-y-2" aria-label="Your answer">
          <textarea
            className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
            rows={3}
            maxLength={MAX_ANSWER_CHARS}
            placeholder={stt.supported ? 'Type your answer, or press the mic and speak…' : 'Type your answer…'}
            aria-label="Your answer"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) sendAnswer() }}
          />
          {stt.interim && <p className="text-xs text-slate-400 italic">…{stt.interim}</p>}
          {stt.error && <p role="alert" className="text-xs text-amber-700">{stt.error}</p>}
          <div className="flex flex-wrap items-center gap-2">
            {stt.supported && (
              <button type="button" onClick={toggleMic} aria-pressed={stt.listening}
                className={`px-3 py-2 rounded-lg text-sm border ${stt.listening ? 'bg-red-50 border-red-200 text-red-700 animate-pulse' : 'border-line hover:bg-elevated'}`}>
                {stt.listening ? '⏹ Stop mic' : '🎤 Speak'}
              </button>
            )}
            <button type="button" onClick={sendAnswer} disabled={loading || !input.trim()}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50">
              Send answer
            </button>
            {editorOn && (
              <button type="button" onClick={sendWithCode} disabled={loading || code.trim() === STARTER.trim()}
                className="border border-accent text-blue-400 px-4 py-2 rounded-lg text-sm hover:bg-elevated disabled:opacity-50">
                Send code
              </button>
            )}
            <button type="button" onClick={onEnd} disabled={loading}
              className="ml-auto text-sm text-slate-500 hover:text-red-600 underline disabled:opacity-50">
              End interview & get scorecard
            </button>
          </div>
          <p className="text-[11px] text-slate-400">Tip: short, structured answers keep the conversation fast. Ctrl+Enter sends.</p>
        </section>
      ) : (
        <p className="text-slate-500 text-sm">
          {status === 'expired' ? 'Turn limit reached, interview closed without a scorecard.' : 'Interview finished.'}
        </p>
      )}
    </div>
  )
}
