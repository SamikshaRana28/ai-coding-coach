// Eye-contact / body-language tracking, 100% IN THE BROWSER (MediaPipe Tasks Vision).
//
// PRIVACY: frames are read from the <video> element, turned into landmark numbers in memory, and thrown
// away. Nothing is drawn to a canvas, saved or uploaded. getMetrics() returns ONLY aggregate numbers.
// The model files (a few MB each) are downloaded from Google's / jsDelivr's CDN the first time.
// To avoid that, copy them into frontend/public/mediapipe/ and change MODEL_URLS / WASM_URL below.
//
// This is "eye contact and delivery feedback", NOT a cheating detector: gaze cannot tell thinking from
// cheating and can be unfair (glasses, disabilities). Integrity data = objective events only.
import { useCallback, useEffect, useRef, useState } from 'react'

const VERSION = '0.10.14'                                   // keep equal to the npm version in package.json
const WASM_URL = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${VERSION}/wasm`
const MODEL_URLS = {
  face: 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
  pose: 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task',
  hands: 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',
}

const SAMPLE_MS = 250                  // ~4 samples per second is plenty for aggregate feedback
const AWAY_MIN_MS = 1500               // a glance shorter than this is normal thinking, not "looking away"
const clamp = (v, lo = 0, hi = 100) => Math.min(hi, Math.max(lo, v))
const round1 = (v) => Math.round(v * 10) / 10
const bs = (list, name) => list.find((c) => c.categoryName === name)?.score ?? 0

function emptyAgg() {
  return {
    startedAt: Date.now(),
    samples: 0, faceSamples: 0, contactSamples: 0,
    lookAways: 0, awayStart: null,
    yawPrev: null, pitchPrev: null, deltaSum: 0, deltaN: 0,
    hasFace: false,
    multiFacePrev: false, multiFaceEvents: 0, multiFaceRun: 0,
    poseSum: 0, poseN: 0,
    handPrev: null, handDist: 0, handMs: 0, handFrames: 0,
    lastT: null,
  }
}

export function useBodyLanguage({ enabled, videoRef }) {
  const [state, setState] = useState('idle')                // idle | loading | running | error
  const [error, setError] = useState(null)
  const [available, setAvailable] = useState({ face: false, pose: false, hands: false })
  const aggRef = useRef(emptyAgg())
  const timerRef = useRef(null)
  const streamRef = useRef(null)
  const modelsRef = useRef({})

  useEffect(() => {
    if (!enabled) return undefined
    let cancelled = false
    aggRef.current = emptyAgg()

    const cleanup = () => {
      clearTimeout(timerRef.current)
      streamRef.current?.getTracks().forEach((t) => t.stop())
      streamRef.current = null
      Object.values(modelsRef.current).forEach((m) => { try { m?.close() } catch { /* ignore */ } })
      modelsRef.current = {}
      if (videoRef.current) videoRef.current.srcObject = null
    }

    const processFrame = (video, now) => {
      const a = aggRef.current
      const m = modelsRef.current
      const dt = a.lastT ? now - a.lastT : SAMPLE_MS
      a.lastT = now
      a.samples += 1

      // ── Face: eye contact, head steadiness, extra faces ──
      if (m.face) {
        const r = m.face.detectForVideo(video, now)
        const faces = r.faceLandmarks?.length || 0
        let contact = false
        if (faces > 0) {
          a.faceSamples += 1
          const shapes = r.faceBlendshapes?.[0]?.categories || []
          const horiz = ((bs(shapes, 'eyeLookOutLeft') - bs(shapes, 'eyeLookInLeft'))
            + (bs(shapes, 'eyeLookInRight') - bs(shapes, 'eyeLookOutRight'))) / 2
          const vert = (bs(shapes, 'eyeLookUpLeft') + bs(shapes, 'eyeLookUpRight')
            - bs(shapes, 'eyeLookDownLeft') - bs(shapes, 'eyeLookDownRight')) / 2
          const mat = r.facialTransformationMatrixes?.[0]?.data
          let yaw = 0
          let pitch = 0
          if (mat) {
            yaw = (Math.asin(clamp(-mat[2], -1, 1)) * 180) / Math.PI
            pitch = (Math.atan2(mat[6], mat[10]) * 180) / Math.PI
            if (a.yawPrev !== null) {
              a.deltaSum += Math.abs(yaw - a.yawPrev) + Math.abs(pitch - a.pitchPrev)
              a.deltaN += 1
            }
            a.yawPrev = yaw
            a.pitchPrev = pitch
          }
          contact = Math.abs(horiz) < 0.35 && Math.abs(vert) < 0.4 && Math.abs(yaw) < 22 && Math.abs(pitch) < 22
        }
        if (contact) {
          a.contactSamples += 1
          if (a.awayStart !== null) {
            if (now - a.awayStart >= AWAY_MIN_MS) a.lookAways += 1
            a.awayStart = null
          }
        } else if (a.awayStart === null) {
          a.awayStart = now
        }
        // more than one face for ~1 s = one event
        a.multiFaceRun = faces > 1 ? a.multiFaceRun + 1 : 0
        const multi = a.multiFaceRun >= 4
        if (multi && !a.multiFacePrev) a.multiFaceEvents += 1
        a.multiFacePrev = multi
      }

      // ── Pose (1 Hz): upright + level shoulders ──
      if (m.pose && a.samples % 4 === 0) {
        const lm = m.pose.detectForVideo(video, now).landmarks?.[0]
        if (lm && lm[11]?.visibility > 0.5 && lm[12]?.visibility > 0.5) {
          const tilt = Math.abs((Math.atan2(lm[11].y - lm[12].y, lm[11].x - lm[12].x) * 180) / Math.PI)
          const tiltDeg = Math.min(tilt, 180 - tilt)
          const width = Math.hypot(lm[11].x - lm[12].x, lm[11].y - lm[12].y) || 1
          const shoulderY = (lm[11].y + lm[12].y) / 2
          const earY = (lm[7].y + lm[8].y) / 2
          const lift = (shoulderY - earY) / width                 // small = slouching / head sunk into shoulders
          const levelScore = clamp(100 - tiltDeg * 6)
          const uprightScore = clamp(((lift - 0.15) / 0.45) * 100)
          a.poseSum += (levelScore + uprightScore) / 2
          a.poseN += 1
        }
      }

      // ── Hands (2 Hz): how much the wrists move ──
      if (m.hands && a.samples % 2 === 0) {
        const hands = m.hands.detectForVideo(video, now).landmarks || []
        if (hands.length > 0) {
          const w = hands[0][0]
          a.handFrames += 1
          if (a.handPrev) {
            a.handDist += Math.hypot(w.x - a.handPrev.x, w.y - a.handPrev.y)
            a.handMs += dt * 2
          }
          a.handPrev = { x: w.x, y: w.y }
        } else {
          a.handPrev = null
        }
      }
    }

    const loop = () => {
      const video = videoRef.current
      if (cancelled) return
      if (video && video.readyState >= 2 && !video.paused) {
        try { processFrame(video, performance.now()) } catch { /* one bad frame never stops the interview */ }
      }
      timerRef.current = setTimeout(loop, SAMPLE_MS)
    }

    const run = async () => {
      setState('loading')
      setError(null)
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 640, height: 480, facingMode: 'user' }, audio: false,
        })
        if (cancelled) { stream.getTracks().forEach((t) => t.stop()); return }
        streamRef.current = stream
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          await videoRef.current.play().catch(() => {})
        }
      } catch {
        if (!cancelled) {
          setState('error')
          setError('Could not open the camera (permission blocked or no camera found). The interview works without it.')
        }
        return
      }

      try {
        const { FaceLandmarker, PoseLandmarker, HandLandmarker, FilesetResolver } = await import('@mediapipe/tasks-vision')
        const fileset = await FilesetResolver.forVisionTasks(WASM_URL)
        const ok = { face: false, pose: false, hands: false }
        // Each model is optional: if one fails to load we still report the others.
        const makers = {
          face: () => FaceLandmarker.createFromOptions(fileset, {
            baseOptions: { modelAssetPath: MODEL_URLS.face }, runningMode: 'VIDEO', numFaces: 2,
            outputFaceBlendshapes: true, outputFacialTransformationMatrixes: true,
          }),
          pose: () => PoseLandmarker.createFromOptions(fileset, {
            baseOptions: { modelAssetPath: MODEL_URLS.pose }, runningMode: 'VIDEO', numPoses: 1,
          }),
          hands: () => HandLandmarker.createFromOptions(fileset, {
            baseOptions: { modelAssetPath: MODEL_URLS.hands }, runningMode: 'VIDEO', numHands: 2,
          }),
        }
        for (const [name, make] of Object.entries(makers)) {
          try { modelsRef.current[name] = await make(); ok[name] = true } catch { /* skip this model */ }
          if (cancelled) return
        }
        if (cancelled) return
        setAvailable(ok)
        aggRef.current.hasFace = ok.face
        if (!ok.face && !ok.pose && !ok.hands) {
          setState('error')
          setError('Could not load the tracking models (offline?). The interview continues without camera feedback.')
          return
        }
        setState('running')
        loop()
      } catch {
        if (!cancelled) {
          setState('error')
          setError('Could not load the tracking models (offline?). The interview continues without camera feedback.')
        }
      }
    }

    run()
    return () => {
      cancelled = true
      cleanup()
      setState('idle')
    }
  }, [enabled, videoRef])

  // Aggregate numbers only. Anything we could not measure is null.
  const getMetrics = useCallback(() => {
    const a = aggRef.current
    let awayNow = 0
    if (a.awayStart !== null && performance.now() - a.awayStart >= AWAY_MIN_MS) awayNow = 1   // still looking away
    const haveFace = a.hasFace && a.samples > 0       // (models are closed after cleanup, so remember it here)
    const handSeconds = a.handMs / 1000
    return {
      eye_contact_pct: haveFace ? round1((a.contactSamples / a.samples) * 100) : null,
      look_away_count: haveFace ? a.lookAways + awayNow : null,
      head_stability_pct: a.deltaN > 20 ? round1(clamp(100 - (a.deltaSum / a.deltaN) * 20)) : null,
      posture_score: a.poseN >= 3 ? round1(a.poseSum / a.poseN) : null,
      hand_movement_level: a.handFrames >= 5 && handSeconds > 2
        ? round1(clamp((a.handDist / handSeconds) * 250)) : null,
      multiple_faces_events: a.multiFaceEvents,
      duration_seconds: Math.round((Date.now() - a.startedAt) / 1000),
    }
  }, [])

  return { state, error, available, getMetrics }
}

// Objective session events (works with the camera off too).
export function useIntegrityEvents(active) {
  const counts = useRef({ tab_switches: 0, focus_lost_events: 0 })
  useEffect(() => {
    if (!active) return undefined
    const onVisibility = () => { if (document.hidden) counts.current.tab_switches += 1 }
    const onBlur = () => { counts.current.focus_lost_events += 1 }
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('blur', onBlur)
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('blur', onBlur)
    }
  }, [active])
  return useCallback(() => ({ ...counts.current }), [])
}
