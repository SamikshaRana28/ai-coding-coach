// Shown BEFORE the camera starts. The camera is never opened without an explicit "Allow".
import { useEffect, useRef } from 'react'

export default function ConsentModal({ onAllow, onDecline }) {
  const allowRef = useRef(null)
  useEffect(() => { allowRef.current?.focus() }, [])

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="consent-title"
      onKeyDown={(e) => { if (e.key === 'Escape') onDecline() }}
      className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4"
    >
      <div className="card max-w-md w-full p-6 space-y-4 shadow-glow">
        <h2 id="consent-title" className="text-xl font-bold">Use your camera for delivery feedback?</h2>
        <ul className="text-sm text-slate-700 space-y-2 list-disc pl-5">
          <li><strong>Your video never leaves this device.</strong> Tracking runs in your browser. Nothing is recorded, uploaded or stored.</li>
          <li>Only a few <strong>summary numbers</strong> are saved at the end: eye-contact %, how often you looked away, head steadiness, posture, hand movement.</li>
          <li>This is <strong>eye contact and delivery feedback</strong> to help you practise. It is not a cheating check, and it can be less accurate with glasses, lighting or disabilities.</li>
          <li>Separately we count simple session events (tab switched, window lost focus, more than one face in view). They are facts, not judgements.</li>
          <li>Voice answers use your browser's speech recognition. Some browsers send that audio to their own speech service.</li>
        </ul>
        <div className="flex flex-col sm:flex-row gap-2">
          <button ref={allowRef} type="button" onClick={onAllow} className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 flex-1">
            Allow camera
          </button>
          <button type="button" onClick={onDecline} className="border border-line px-4 py-2 rounded-lg text-slate-700 hover:bg-elevated flex-1">
            Continue without camera
          </button>
        </div>
      </div>
    </div>
  )
}
