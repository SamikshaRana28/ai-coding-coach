import { useState } from 'react'
import Editor from '@monaco-editor/react'
import { analyzeCode } from '../api'

export default function CodeAnalyzer() {
  const [question, setQuestion] = useState('Two Sum')
  const [code, setCode] = useState('def two_sum(nums, target):\n    for i in range(len(nums)):\n        for j in range(i+1, len(nums)):\n            if nums[i] + nums[j] == target:\n                return [i, j]')
  const [language, setLanguage] = useState('python')
  const [topic, setTopic] = useState('general')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleAnalyze = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await analyzeCode({ question, code, language, topic, difficulty: 'medium', user_id: 1 })
      setResult(res.data)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">💻 Code Analyzer</h1>
        <p className="text-slate-500 mt-1">Paste your solution and get AI-powered feedback</p>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium block mb-1">Problem / Question</label>
            <input
              className="w-full border border-slate-300 rounded-lg px-3 py-2"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. Two Sum"
            />
          </div>

          <div>
            <label className="text-sm font-medium block mb-1">Language</label>
            <select
              className="w-full border border-slate-300 rounded-lg px-3 py-2"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
            >
              <option value="python">Python</option>
              <option value="javascript">JavaScript</option>
              <option value="java">Java</option>
              <option value="cpp">C++</option>
            </select>



            <div>
            <label className="text-sm font-medium block mb-1">Topic</label>
            <input
              className="w-full border border-slate-300 rounded-lg px-3 py-2"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. arrays, dp, graphs, linked lists"
            />
          </div>


          
          </div>

          <div>
            <label className="text-sm font-medium block mb-1">Your Code</label>
            <div className="border border-slate-300 rounded-lg overflow-hidden">
              <Editor
                height="300px"
                language={language}
                value={code}
                onChange={(val) => setCode(val ?? '')}
                theme="vs-dark"
                options={{ minimap: { enabled: false }, fontSize: 14 }}
              />
            </div>
          </div>

          <button
            onClick={handleAnalyze}
            disabled={loading}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Analyzing...' : 'Analyze Code'}
          </button>
        </div>

        <div className="space-y-4">
          <h2 className="font-bold text-lg">AI Feedback</h2>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm">
              {error}
            </div>
          )}

          {!result && !error && !loading && (
            <div className="bg-slate-100 rounded-lg p-6 text-slate-400 text-center">
              Run analysis to see feedback here
            </div>
          )}

          {loading && (
            <div className="bg-slate-100 rounded-lg p-6 text-slate-400 text-center animate-pulse">
              Calling AI model...
            </div>
          )}

          {result && (
            <div className="space-y-3">
              <FeedbackCard title="⏱️ Time Complexity" content={result.time_complexity} color="blue" />
              <FeedbackCard title="💾 Space Complexity" content={result.space_complexity} color="purple" />
              <FeedbackCard title="🐛 Bugs" content={result.bugs} color="red" />
              <FeedbackCard title="✨ Better Approach" content={result.better_approach} color="green" />
              <FeedbackCard title="🔗 Similar Questions" content={result.similar_questions} color="amber" />
              <FeedbackCard title="🎤 Interviewer Questions" content={result.interviewer_questions} color="indigo" />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function FeedbackCard({ title, content, color }) {
  const colors = {
    blue: 'border-blue-200 bg-blue-50',
    purple: 'border-purple-200 bg-purple-50',
    red: 'border-red-200 bg-red-50',
    green: 'border-green-200 bg-green-50',
    amber: 'border-amber-200 bg-amber-50',
    indigo: 'border-indigo-200 bg-indigo-50',
  }
  return (
    <div className={`rounded-lg p-4 border ${colors[color]}`}>
      <h3 className="font-semibold text-sm mb-1">{title}</h3>
      <p className="text-sm text-slate-700 whitespace-pre-wrap">{content}</p>
    </div>
  )
}