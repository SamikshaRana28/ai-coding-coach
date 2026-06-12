import { Routes, Route, NavLink } from 'react-router-dom'
import ModelEvaluation from './pages/ModelEvaluation'
import CodeAnalyzer from './pages/CodeAnalyzer'
import Dashboard from './pages/Dashboard'
import SimilarQuestions from './pages/SimilarQuestions'
import TopicTracker from './pages/TopicTracker'

const navItems = [
  { to: '/', label: 'Model Evaluation' },
  { to: '/analyzer', label: 'Code Analyzer' },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/similar', label: 'Similar Questions' },
  { to: '/topics', label: 'Topic Tracker' },
]

function App() {
  return (
    <div className="min-h-screen bg-slate-50">
      <nav className="bg-slate-900 text-white px-6 py-4 flex gap-6 items-center">
        <span className="font-bold text-lg">🤖 AI Coding Coach</span>
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `text-sm ${isActive ? 'text-blue-400 font-semibold' : 'text-slate-300 hover:text-white'}`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <main className="p-6 max-w-6xl mx-auto">
        <Routes>
          <Route path="/" element={<ModelEvaluation />} />
          <Route path="/analyzer" element={<CodeAnalyzer />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/similar" element={<SimilarQuestions />} />
          <Route path="/topics" element={<TopicTracker />} />
        </Routes>
      </main>
    </div>
  )
}

export default App