// Flame + current / longest streak, and the 7-dot row of the last 7 days.
export function StreakBadge({ streak }) {
  const current = streak?.current_streak ?? 0
  return (
    <div className="flex items-center gap-3">
      <span className="text-3xl" aria-hidden="true">{current > 0 ? '🔥' : '🕯️'}</span>
      <div>
        <div className="text-2xl font-bold leading-none">
          {current} day{current === 1 ? '' : 's'}
        </div>
        <div className="text-xs text-slate-500">current streak · longest {streak?.longest_streak ?? 0}</div>
      </div>
    </div>
  )
}

export function WeekDots({ week = [] }) {
  const done = week.filter((d) => d.active).length
  return (
    <div role="img" aria-label={`Active on ${done} of the last 7 days`} className="flex gap-2">
      {week.map((d) => (
        <div key={d.date} className="flex flex-col items-center gap-1" title={`${d.weekday} ${d.date}${d.active ? ': active' : ''}`}>
          <span className={`w-4 h-4 rounded-full ${d.active ? 'bg-orange-500' : 'bg-slate-200'}`} />
          <span className="text-[10px] text-slate-400">{d.weekday.slice(0, 1)}</span>
        </div>
      ))}
    </div>
  )
}
