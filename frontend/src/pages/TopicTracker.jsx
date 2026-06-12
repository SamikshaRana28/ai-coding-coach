import { useState } from 'react'
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer, Legend } from 'recharts'

const defaultStats = {
  arrays: 25, graphs: 10, dp: 8, trees: 15, strings: 20, math: 5,
}

export default function TopicTracker() {
  const [stats, setStats] = useState(defaultStats)

  const handleChange = (key, value) => {
    setStats((prev) => ({ ...prev, [key]: parseInt(value) || 0 }))
  }

  const data = Object.entries(stats).map(([topic, value]) => ({ topic: topic.toUpperCase(), value }))
  const weakest = Object.entries(stats).sort((a, b) => a[1] - b[1])[0]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">🕸️ Topic Tracker</h1>
        <p className="text-slate-500 mt-1">Visual breakdown of your performance across 6 core topics</p>
      </div>

      <div className="grid md:grid-cols-3 gap-6">
        <div className="bg-white rounded-xl p-6 border border-slate-200 space-y-3">
          <h2 className="font-bold">Problems Solved</h2>
          {Object.entries(defaultStats).map(([key]) => (
            <div key={key}>
              <label className="text-xs text-slate-500 uppercase">{key}</label>
              <input
                type="number"
                className="w-full border border-slate-300 rounded px-2 py-1 text-sm"
                value={stats[key]}
                onChange={(e) => handleChange(key, e.target.value)}
              />
            </div>
          ))}
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mt-2">
            <p className="text-sm">⚠️ Weakest: <span className="font-semibold uppercase">{weakest[0]}</span> ({weakest[1]} solved)</p>
          </div>
        </div>

        <div className="md:col-span-2 bg-white rounded-xl p-6 border border-slate-200">
          <ResponsiveContainer width="100%" height={400}>
            <RadarChart data={data}>
              <PolarGrid />
              <PolarAngleAxis dataKey="topic" />
              <PolarRadiusAxis />
              <Radar name="Problems Solved" dataKey="value" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.4} />
              <Legend />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}