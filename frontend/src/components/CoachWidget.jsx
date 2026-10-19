// Floating chat panel (opened by the round Coach button, or by "Ask Coach about this problem").
// It stays MOUNTED (just hidden) when closed, so the conversation and its state survive page changes.
// Desktop: 380 x 560 panel bottom-right. Mobile: full screen.
import CoachChat from './CoachChat'

export default function CoachWidget({ open, onClose, problem, getCode, onReply }) {
  return (
    <div
      role="dialog"
      aria-label="Coach chat"
      aria-hidden={!open}
      onKeyDown={(e) => { if (e.key === 'Escape') onClose() }}
      className={`${open ? 'flex' : 'hidden'} fixed z-40 bg-surface border border-line shadow-glow flex-col
        inset-0 sm:inset-auto sm:bottom-4 sm:right-4 sm:w-[380px] sm:h-[560px] sm:max-h-[85vh] sm:rounded-2xl`}
    >
      <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-line">
        <div className="font-bold text-sm flex items-center gap-2">
          <span aria-hidden="true">🤖</span> Coach
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close Coach chat"
          className="text-slate-500 hover:text-slate-900 px-2 py-1 rounded"
        >
          ✕
        </button>
      </div>
      <CoachChat active={open} problem={problem} getCode={getCode} onReply={onReply} onNavigate={onClose} className="flex-1" />
    </div>
  )
}
