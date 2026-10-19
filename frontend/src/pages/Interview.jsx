// Interview Practice (lives inside the Coach page, also reachable at /interview).
// Flow: choose round (+ resume PDF) -> consent (if camera) -> live interview with voice/camera -> scorecard.
// Backend: /interview/* (rounds, resume extract, metrics). Camera tracking runs in the browser; only aggregate numbers are sent.
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  startInterview, sendAnswer, getInterview, getScorecard, getInterviewTopics,
  saveInterviewMetrics, deleteInterviewResume,
} from '../api'
import { useAuth } from '../auth/useAuth'
import { friendlyError } from '../components/ui'
import RoundSetup from '../interview/RoundSetup'
import InterviewRoom from '../interview/InterviewRoom'
import Scorecard from '../interview/Scorecard'
import ConsentModal from '../interview/ConsentModal'
import { useBodyLanguage, useIntegrityEvents } from '../interview/useBodyLanguage'
import { speechSupport } from '../interview/useSpeech'

const END_MESSAGE = 'Please end the interview now and give me my scorecard.'

export default function Interview() {
  const { user } = useAuth()
  const STORAGE_KEY = `interview_session_id_${user.id}`        // each user has their own session
  const [topics, setTopics] = useState(['arrays'])
  const [sessionId, setSessionId] = useState(null)
  const [round, setRound] = useState('dsa')
  const [messages, setMessages] = useState([])
  const [status, setStatus] = useState('idle')                 // idle | active | finished | expired
  const [turns, setTurns] = useState({ used: 0, max: 12 })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [scorecard, setScorecard] = useState(null)
  const [restored, setRestored] = useState(false)
  const [voiceOut, setVoiceOut] = useState(false)
  const [cameraOn, setCameraOn] = useState(false)
  const [pendingStart, setPendingStart] = useState(null)       // setup params waiting for the consent screen
  const [consentFor, setConsentFor] = useState(null)           // 'start' | 'toggle' | null

  const videoRef = useRef(null)
  const speechStatsRef = useRef(null)
  const active = status === 'active'
  const body = useBodyLanguage({ enabled: cameraOn && active, videoRef })
  const getIntegrity = useIntegrityEvents(active)
  const { getMetrics: getBodyMetrics } = body

  // Everything we ever send about delivery: aggregate numbers, no media.
  const buildMetrics = useCallback(() => {
    const speech = speechStatsRef.current?.() || {}
    const cam = getBodyMetrics()
    return {
      camera_used: cameraOn && cam.eye_contact_pct !== null,
      voice_used: speech.words > 0,
      duration_seconds: cam.duration_seconds,
      eye_contact_pct: cam.eye_contact_pct,
      look_away_count: cam.look_away_count,
      head_stability_pct: cam.head_stability_pct,
      posture_score: cam.posture_score,
      hand_movement_level: cam.hand_movement_level,
      multiple_faces_events: cam.multiple_faces_events,
      filler_words_per_min: speech.filler_words_per_min ?? null,
      speaking_pace_wpm: speech.speaking_pace_wpm ?? null,
      ...getIntegrity(),
    }
  }, [cameraOn, getBodyMetrics, getIntegrity])

  const pushMetrics = useCallback(async (id, snapshot) => {
    try { await saveInterviewMetrics(id, snapshot || buildMetrics()) } catch { /* feedback is a bonus: never block the interview */ }
  }, [buildMetrics])

  // Save a snapshot every 30 s while active, so closing the tab does not lose the numbers.
  useEffect(() => {
    if (!active || !sessionId) return undefined
    const t = setInterval(() => pushMetrics(sessionId), 30000)
    return () => clearInterval(t)
  }, [active, sessionId, pushMetrics])

  // Reload / server restart: the session comes back from the DB.
  useEffect(() => {
    getInterviewTopics().then((r) => setTopics(r.data.topics)).catch(() => {})
    const saved = localStorage.getItem(STORAGE_KEY)
    if (!saved) return
    getInterview(saved)
      .then((r) => {
        setSessionId(r.data.session_id)
        setRound(r.data.round || 'dsa')
        setMessages(r.data.history)
        setStatus(r.data.status)
        setRestored(true)
        setTurns({ used: r.data.turns_used, max: r.data.max_turns })
        if (r.data.status === 'finished') {
          getScorecard(saved).then((sc) => setScorecard(sc.data)).catch(() => {})
        }
      })
      .catch(() => localStorage.removeItem(STORAGE_KEY))
  }, [STORAGE_KEY])

  const doStart = async ({ round: r, topic, resumeText, voice }, withCamera) => {
    setLoading(true)
    setError(null)
    setScorecard(null)
    try {
      const res = await startInterview({ topic, round: r, resume_text: resumeText })
      localStorage.setItem(STORAGE_KEY, res.data.session_id)
      setSessionId(res.data.session_id)
      setRound(res.data.round || r)
      setMessages([{ role: 'assistant', content: res.data.reply }])
      setTurns({ used: 0, max: res.data.max_turns })
      setRestored(false)
      setVoiceOut(Boolean(voice) && speechSupport().tts)
      setCameraOn(withCamera)
      setStatus(res.data.status)
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
      setPendingStart(null)
    }
  }

  const handleStart = (params) => {
    if (params.camera) {
      setPendingStart(params)
      setConsentFor('start')
    } else {
      doStart(params, false)
    }
  }

  const handleSend = async (text) => {
    setLoading(true)
    setError(null)
    setMessages((m) => [...m, { role: 'user', content: text }])
    try {
      const res = await sendAnswer(sessionId, { answer: text })
      const ended = res.data.status !== 'active'
      // Take the delivery snapshot BEFORE the status change stops the camera.
      const snapshot = ended ? buildMetrics() : null
      setMessages((m) => [...m, { role: 'assistant', content: res.data.reply }])
      setStatus(res.data.status)
      setTurns({ used: res.data.turns_used, max: res.data.max_turns })
      if (ended) {
        await pushMetrics(sessionId, snapshot)
        if (res.data.status === 'finished') {
          getScorecard(sessionId).then((r) => setScorecard(r.data)).catch(() => {})
        }
      }
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  const handleNew = () => {
    if (sessionId && active && !window.confirm('Leave this interview? It will stay unfinished.')) return
    if (sessionId) deleteInterviewResume(sessionId).catch(() => {})
    localStorage.removeItem(STORAGE_KEY)
    setSessionId(null)
    setMessages([])
    setStatus('idle')
    setScorecard(null)
    setError(null)
    setCameraOn(false)
    setRestored(false)
  }

  const toggleCamera = () => {
    if (cameraOn) setCameraOn(false)
    else setConsentFor('toggle')
  }

  const onAllow = () => {
    if (consentFor === 'start' && pendingStart) doStart(pendingStart, true)
    else setCameraOn(true)
    setConsentFor(null)
  }
  const onDecline = () => {
    if (consentFor === 'start' && pendingStart) doStart(pendingStart, false)
    setConsentFor(null)
  }

  return (
    <div className="space-y-5">
      {status === 'idle' ? (
        <>
          <div>
            <h1 className="text-2xl font-bold">🎤 Interview Practice</h1>
            <p className="text-slate-500 mt-1">
              An AI interviewer asks questions, follows up, never hands you the answer, and scores you. Optional voice and camera give delivery feedback.
            </p>
          </div>
          <RoundSetup topics={topics} onStart={handleStart} loading={loading} error={error} />
        </>
      ) : (
        <>
          <div className="flex justify-end">
            <button type="button" onClick={handleNew} className="text-sm text-blue-400 underline">New interview</button>
          </div>
          <InterviewRoom
            round={round}
            messages={messages}
            status={status}
            turns={turns}
            loading={loading}
            error={error}
            restored={restored}
            onSend={handleSend}
            onEnd={() => handleSend(END_MESSAGE)}
            voiceOut={voiceOut}
            onToggleVoice={() => setVoiceOut((v) => !v)}
            cameraOn={cameraOn}
            camera={body}
            onToggleCamera={toggleCamera}
            videoRef={videoRef}
            speechStatsRef={speechStatsRef}
          />
          {scorecard && <Scorecard card={scorecard} />}
          {status === 'finished' && !scorecard && <p className="text-sm text-slate-500 animate-pulse">Preparing your scorecard…</p>}
        </>
      )}
      {consentFor && <ConsentModal onAllow={onAllow} onDecline={onDecline} />}
    </div>
  )
}
