import { useState } from 'react'
import { getRecommendations, predictDifficulty } from '../api'

export default function SimilarQuestions() {
  const [title, setTitle] = useState('Two Sum')
  const [results, setResults] = useState(null)
  const [difficulty, setDifficulty] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSearch = async () => {
    setLoading(true)
    setError(null)
    setResults(null)
    setDifficulty(null)
    try {
      const [recRes, diffRes] = await Promise.all([
        getRecommendations({ title }),
        predictDifficulty({ title, description: '' }),
      ])
      setResults(recRes.data.similar_questions)
      setDifficulty(diffRes.data)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  const diffColor = (d) => ({
    Easy: 'bg-green-100 text-green-700',
    Medium: 'bg-amber-100 text-amber-700',
    Hard: 'bg-red-100 text-red-700',
  }[d] || 'bg-slate-100 text-slate-700')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">🔍 Similar Questions</h1>
        <p className="text-slate-500 mt-1">NLP-powered recommendations using Sentence Transformers</p>
      </div>

      <div className="flex gap-3">
        <input
          className="flex-1 border border-slate-300 rounded-lg px-4 py-2"
          placeholder="Enter a question title, e.g. Two Sum"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
        />
        <button
          onClick={handleSearch}
          disabled={loading}
          className="bg-blue-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Searching...' : 'Search'}
        </button>
      </div>

      {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm">{error}</div>}

      {difficulty && (
        <div className="bg-white rounded-xl p-4 border border-slate-200 flex items-center gap-3">
          <span className="text-sm font-medium">Predicted Difficulty for "{title}":</span>
          <span className={`px-3 py-1 rounded-full text-sm font-semibold ${diffColor(difficulty.predicted_difficulty)}`}>
            {difficulty.predicted_difficulty}
          </span>
          <span className="text-xs text-slate-400">({(difficulty.confidence * 100).toFixed(0)}% confidence)</span>
        </div>
      )}

      {results && (
        <div className="grid md:grid-cols-3 gap-4">
          {results.map((q, i) => (
            <div key={i} className="bg-white rounded-xl p-4 border border-slate-200 space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold">{q.title}</h3>
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${diffColor(q.difficulty)}`}>
                  {q.difficulty}
                </span>
              </div>
              <p className="text-xs text-slate-500 line-clamp-2">{q.topics}</p>
              <div className="flex items-center justify-between text-xs">
  <span className="text-slate-400">
    Similarity: {(q.similarity_score * 100).toFixed(0)}%
  </span>

  <a
    href={`https://leetcode.com/problems/${q.title
      .toLowerCase()
      .replace(/\s+/g, '-')}/`}
    target="_blank"
    rel="noreferrer"
    className="text-blue-600 hover:underline"
  >
    LeetCode →
  </a>
</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}