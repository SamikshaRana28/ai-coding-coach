import { useState } from 'react'
import { getScore, predictWeakTopic } from '../api'

const defaultStats = {
  arrays_solved: 25, graphs_solved: 10, dp_solved: 8,
  trees_solved: 15, strings_solved: 20, math_solved: 5,
  avg_attempts: 2.5, acceptance_rate: 0.6,
}

export default function Dashboard() {
  const [stats, setStats] = useState(defaultStats)
  const [score, setScore] = useState(null)
  const [weakTopic, setWeakTopic] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleChange = (key, value) => {
    setStats((prev) => ({ ...prev, [key]: parseFloat(value) || 0 }))
  }

  const handleCalculate = async () => {
    setLoading(true)
    try {
      const [scoreRes, weakRes] = await Promise.all([
        getScore(stats),
        predictWeakTopic(stats),
      ])
      setScore(scoreRes.data)
      setWeakTopic(weakRes.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const totalSolved = stats.arrays_solved + stats.graphs_solved + stats.dp_solved +
    stats.trees_solved + stats.strings_solved + stats.math_solved

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">📈 Dashboard</h1>
        <p className="text-slate-500 mt-1">Your interview readiness at a glance</p>
      </div>

      <div className="grid md:grid-cols-3 gap-6">
        <div className="md:col-span-1 bg-white rounded-xl p-6 border border-slate-200 space-y-3">
          <h2 className="font-bold">Your Stats</h2>
          {Object.entries(defaultStats).map(([key]) => (
            <div key={key}>
              <label className="text-xs text-slate-500">{key.replace(/_/g, ' ')}</label>
              <input
                type="number"
                step={key.includes('rate') || key.includes('attempts') ? '0.1' : '1'}
                className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
                value={stats[key]}
                onChange={(e) => handleChange(key, e.target.value)}
              />
            </div>
          ))}
          <button
            onClick={handleCalculate}
            disabled={loading}
            className="w-full bg-blue-600 text-white py-2 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Calculating...' : 'Calculate'}
          </button>
        </div>

        <div className="md:col-span-2 space-y-6">
          {score ? (
            <div className="bg-white rounded-xl p-6 border border-slate-200 flex items-center gap-8">
              <ScoreGauge score={score.total_score} />
              <div>
                <h2 className="text-2xl font-bold">{score.level}</h2>
                <p className="text-slate-500 mt-1">{score.message}</p>
                <div className="grid grid-cols-2 gap-3 mt-4 text-sm">
                  {Object.entries(score.breakdown).map(([k, v]) => (
                    <div key={k}>
                      <span className="text-slate-400">{k.replace(/_/g, ' ')}: </span>
                      <span className="font-semibold">{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-slate-100 rounded-xl p-12 text-center text-slate-400">
              Enter your stats and click Calculate
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <StatCard label="Total Solved" value={totalSolved} />
            <StatCard label="Acceptance Rate" value={`${(stats.acceptance_rate * 100).toFixed(0)}%`} />
          </div>

          {weakTopic && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <h3 className="font-semibold">⚠️ Weakest Topic: <span className="capitalize">{weakTopic.weak_topic}</span></h3>
              <p className="text-sm text-slate-600 mt-1">Confidence: {(weakTopic.confidence * 100).toFixed(0)}%</p>
              <div className="mt-2 space-y-1">
                {Object.entries(weakTopic.all_probabilities).map(([topic, prob]) => (
                  <div key={topic} className="flex items-center gap-2 text-xs">
                    <span className="w-20 capitalize">{topic}</span>
                    <div className="flex-1 bg-slate-200 rounded-full h-2 overflow-hidden">
                      <div className="bg-amber-500 h-2 rounded-full" style={{ width: `${prob * 100}%` }}></div>
                    </div>
                    <span className="w-10 text-right">{(prob * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function ScoreGauge({ score }) {
  const radius = 60
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (score / 100) * circumference
  const color = score >= 80 ? '#22c55e' : score >= 60 ? '#3b82f6' : score >= 40 ? '#f59e0b' : '#ef4444'

  return (
    <div className="relative w-36 h-36 shrink-0">
      <svg className="w-36 h-36 -rotate-90">
        <circle cx="72" cy="72" r={radius} stroke="#e2e8f0" strokeWidth="12" fill="none" />
        <circle
          cx="72" cy="72" r={radius}
          stroke={color} strokeWidth="12" fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.5s ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-3xl font-bold">{score}</span>
      </div>
    </div>
  )
}

function StatCard({ label, value }) {
  return (
    <div className="bg-white rounded-xl p-4 border border-slate-200">
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-sm text-slate-500">{label}</div>
    </div>
  )
}