import { SCORE_LABELS, ROUNDS } from './rounds'

const KEYS = ['approach', 'complexity', 'edge_cases', 'communication']

function Meter({ label, value, suffix = '%', hint }) {
  if (value === null || value === undefined) return null
  return (
    <div className="bg-elevated rounded-lg p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-lg font-semibold">{value}{suffix}</div>
      {hint && <div className="text-[11px] text-slate-400">{hint}</div>}
    </div>
  )
}

export default function Scorecard({ card }) {
  const labels = SCORE_LABELS[card.round] || SCORE_LABELS.dsa
  const roundMeta = ROUNDS.find((r) => r.id === card.round)
  const d = card.delivery
  const m = d?.metrics || {}

  return (
    <div className="card p-5 space-y-5" aria-label="Interview scorecard">
      <div>
        <h2 className="text-xl font-bold">Scorecard: {card.total}/{card.out_of}</h2>
        {roundMeta && <p className="text-xs text-slate-500">{roundMeta.icon} {roundMeta.title} round</p>}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        {KEYS.map((k) => (
          <div key={k} className="bg-elevated rounded-lg p-3">
            <div className="text-slate-500 text-xs">{labels[k]}</div>
            <div className="text-lg font-semibold">{card[k]}/5</div>
          </div>
        ))}
      </div>

      {card.weak_patterns?.length > 0 && (
        <p className="text-sm"><span className="font-medium">Weak patterns:</span> {card.weak_patterns.join(', ')}</p>
      )}
      {card.summary && <p className="text-sm text-slate-600">{card.summary}</p>}

      <section aria-label="Communication and body language" className="border-t border-line pt-4 space-y-3">
        <h3 className="font-semibold">🎙️ Communication and body language</h3>
        {!d ? (
          <p className="text-sm text-slate-500">
            No delivery data was collected. Turn on voice or camera next time to get eye-contact, pace and filler-word feedback.
          </p>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Meter label="Eye contact" value={m.eye_contact_pct} />
              <Meter label="Looked away (times)" value={m.look_away_count} suffix="" />
              <Meter label="Head steadiness" value={m.head_stability_pct} />
              <Meter label="Posture" value={m.posture_score} />
              <Meter label="Hand movement" value={m.hand_movement_level} hint="0 still · 100 very busy" />
              <Meter label="Filler words / min" value={m.filler_words_per_min} suffix="" />
              <Meter label="Speaking pace" value={m.speaking_pace_wpm} suffix=" wpm" hint="comfortable: 120-160" />
            </div>
            <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700">
              {d.tips.map((t) => <li key={t}>{t}</li>)}
            </ul>
            {(d.integrity.tab_switches > 0 || d.integrity.focus_lost_events > 0 || d.integrity.multiple_faces_events > 0) && (
              <div className="text-xs text-slate-500 border border-line rounded-lg p-3 space-y-1">
                <div className="font-medium text-slate-600">Session events (facts only)</div>
                <div>Tab switched: {d.integrity.tab_switches} · Window lost focus: {d.integrity.focus_lost_events} · More than one face in view: {d.integrity.multiple_faces_events}</div>
              </div>
            )}
            {d.notes.map((n) => <p key={n} className="text-xs text-slate-500">{n}</p>)}
            <p className="text-[11px] text-slate-400">
              Delivery feedback runs on your device; no video was uploaded or stored. It is a practice aid and can be less accurate with glasses, lighting or disabilities.
            </p>
          </>
        )}
      </section>
    </div>
  )
}
