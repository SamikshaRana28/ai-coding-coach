import { Routes, Route, NavLink, Outlet } from 'react-router-dom'
import ModelEvaluation from './pages/ModelEvaluation'
import CodeAnalyzer from './pages/CodeAnalyzer'
import Dashboard from './pages/Dashboard'
import SimilarQuestions from './pages/SimilarQuestions'
import TopicTracker from './pages/TopicTracker'
import Progress from './pages/Progress'
import Interview from './pages/Interview'
import Login from './pages/Login'
import Signup from './pages/Signup'
import ProtectedRoute from './auth/ProtectedRoute'
import { useAuth } from './auth/useAuth'

const navItems = [
  { to: '/', label: 'Model Evaluation' },
  { to: '/analyzer', label: 'Code Analyzer' },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/similar', label: 'Similar Questions' },
  { to: '/topics', label: 'Topic Tracker' },
  { to: '/progress', label: 'Progress' },
  { to: '/interview', label: 'Mock Interview' },
]

// Navbar + page container shown to logged-in users only.
function AppLayout() {
  const { user, logout } = useAuth()

  return (
    <div className="min-h-screen bg-slate-50">
      <nav className="bg-slate-900 text-white px-6 py-4 flex flex-wrap gap-x-6 gap-y-2 items-center">
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
        <div className="ml-auto flex items-center gap-3">
          <span className="text-sm text-slate-300">{user.first_name || user.name || user.email}</span>
          <button
            onClick={logout}
            className="text-sm px-3 py-1 rounded-md border border-slate-600 text-slate-200 hover:bg-slate-800"
          >
            Logout
          </button>
        </div>
      </nav>
      <main className="p-6 max-w-6xl mx-auto">
        <Outlet />
      </main>
    </div>
  )
}

function App() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />

      {/* Everything else requires login */}
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<ModelEvaluation />} />
          <Route path="/analyzer" element={<CodeAnalyzer />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/similar" element={<SimilarQuestions />} />
          <Route path="/topics" element={<TopicTracker />} />
          <Route path="/progress" element={<Progress />} />
          <Route path="/interview" element={<Interview />} />
        </Route>
      </Route>
    </Routes>
  )
}

export default App
