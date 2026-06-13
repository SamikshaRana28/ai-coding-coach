import { useEffect, useState } from 'react'
import { getProgress } from '../api'
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from 'recharts'

export default function Progress() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    getProgress(1)
      .then(res => setData(res.data))
      .catch(e => setError(e.message))
  }, [])

  if (error) return <div className="text-red-600">Error loading progress: {error}</div>
  if (!data) return <div>Loading progress...</div>

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">📅 Progress Over Time</h1>
        <p className="text-slate-500 mt-1">Weekly readiness score trend ({data.weeks} weeks)</p>
      </div>
      <div className="bg-white rounded-xl p-6 border border-slate-200">
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data.progress}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="week" />
            <YAxis domain={[0, 100]} />
            <Tooltip />
            <Line type="monotone" dataKey="score" stroke="#3b82f6" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="bg-green-50 border border-green-200 rounded-xl p-4">
        <p className="text-sm">
          📈 Score improved from <span className="font-bold">{data.progress[0].score}</span> to{' '}
          <span className="font-bold">{data.progress[data.progress.length - 1].score}</span> over {data.weeks} weeks
        </p>
      </div>
    </div>
  )
}