import { useEffect, useState } from 'react'
import { getProgress } from '../api'
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from 'recharts'

export default function Progress() {
  const [data, setData] = useState(null)
  useEffect(() => { getProgress(1).then(res => setData(res.data)).catch(console.error) }, [])

  if (!data) return <div>Loading progress...</div>

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">📅 Progress Over Time</h1>
        <p className="text-slate-500 mt-1">Weekly readiness score trend</p>
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
    </div>
  )
}