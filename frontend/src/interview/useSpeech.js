// Browser voice for the interview: speech-to-text (Web Speech API) and text-to-speech (speechSynthesis).
// No audio is recorded or uploaded by us. (Chrome's built-in recogniser may send audio to the browser
// vendor's speech service; the consent screen says so.) We only keep word counts for pace / filler feedback.
import { useCallback, useEffect, useRef, useState } from 'react'

const getRecognitionClass = () =>
  typeof window === 'undefined' ? null : window.SpeechRecognition || window.webkitSpeechRecognition || null

export const speechSupport = () => ({
  stt: Boolean(getRecognitionClass()),
  tts: typeof window !== 'undefined' && 'speechSynthesis' in window,
})

// um / uh / er / hmm / you know / I mean / basically / actually / sort of / kind of
const FILLER = /\b(um+|uh+|er+|erm|ah+|hmm+|you know|i mean|basically|actually|sort of|kind of)\b/gi
export const countFillers = (text) => (text.match(FILLER) || []).length
export const countWords = (text) => (text.trim().match(/\S+/g) || []).length

export function useSpeechRecognition({ onFinal, lang = 'en-IN' }) {
  const Rec = getRecognitionClass()
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const [error, setError] = useState(null)
  const recRef = useRef(null)
  const wantRef = useRef(false)
  const onFinalRef = useRef(onFinal)
  const statsRef = useRef({ words: 0, fillers: 0, speakingMs: 0 })
  const utterStartRef = useRef(null)

  useEffect(() => { onFinalRef.current = onFinal }, [onFinal])

  const stop = useCallback(() => {
    wantRef.current = false
    setListening(false)
    setInterim('')
    try { recRef.current?.stop() } catch { /* already stopped */ }
  }, [])

  const start = useCallback(() => {
    if (!Rec || wantRef.current) return
    setError(null)
    const rec = new Rec()
    rec.continuous = true
    rec.interimResults = true
    rec.lang = lang
    rec.onresult = (event) => {
      let interimText = ''
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const res = event.results[i]
        const text = res[0].transcript
        if (utterStartRef.current === null) utterStartRef.current = Date.now()
        if (res.isFinal) {
          const s = statsRef.current
          s.words += countWords(text)
          s.fillers += countFillers(text)
          s.speakingMs += Date.now() - utterStartRef.current
          utterStartRef.current = null
          onFinalRef.current?.(text.trim())
        } else {
          interimText += text
        }
      }
      setInterim(interimText)
    }
    rec.onerror = (e) => {
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
        wantRef.current = false
        setListening(false)
        setError('Microphone permission was blocked. Allow it in the browser address bar, or type your answer.')
      } else if (e.error !== 'no-speech' && e.error !== 'aborted') {
        setError(`Voice input problem (${e.error}). You can still type.`)
      }
    }
    rec.onend = () => {
      // Chrome stops after a pause in speech. Restart while the user still wants to talk.
      if (wantRef.current) {
        try { rec.start() } catch { /* restarting too fast: next onend retries */ }
      } else {
        setListening(false)
      }
    }
    recRef.current = rec
    wantRef.current = true
    try {
      rec.start()
      setListening(true)
    } catch {
      wantRef.current = false
    }
  }, [Rec, lang])

  useEffect(() => () => {
    wantRef.current = false
    try { recRef.current?.abort() } catch { /* ignore */ }
  }, [])

  // Aggregates only. Pace needs at least ~5 s of speech to mean anything.
  const getStats = useCallback(() => {
    const { words, fillers, speakingMs } = statsRef.current
    const minutes = speakingMs / 60000
    if (speakingMs < 5000) return { filler_words_per_min: null, speaking_pace_wpm: null, words }
    return {
      filler_words_per_min: Math.round((fillers / minutes) * 10) / 10,
      speaking_pace_wpm: Math.round(words / minutes),
      words,
    }
  }, [])

  return { supported: Boolean(Rec), listening, interim, error, start, stop, getStats }
}

export function useSpeechSynthesis() {
  const supported = typeof window !== 'undefined' && 'speechSynthesis' in window
  const [speaking, setSpeaking] = useState(false)

  const cancel = useCallback(() => {
    if (!supported) return
    window.speechSynthesis.cancel()
    setSpeaking(false)
  }, [supported])

  const speak = useCallback((text) => {
    if (!supported || !text) return
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text.slice(0, 600))     // interviewer replies are short; cap anyway
    const voices = window.speechSynthesis.getVoices()
    const voice = voices.find((v) => /en[-_](IN|GB|US)/i.test(v.lang)) || voices.find((v) => v.lang?.startsWith('en'))
    if (voice) u.voice = voice
    u.rate = 1.05
    u.onstart = () => setSpeaking(true)
    u.onend = () => setSpeaking(false)
    u.onerror = () => setSpeaking(false)
    window.speechSynthesis.speak(u)
  }, [supported])

  useEffect(() => () => { if (supported) window.speechSynthesis.cancel() }, [supported])

  return { supported, speaking, speak, cancel }
}
