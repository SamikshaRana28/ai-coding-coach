import { Routes, Route, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from './auth/useAuth'
import ProtectedRoute from './auth/ProtectedRoute'
import Login from './pages/Login'
import Signup from './pages/Signup'
import ModelEvaluation from './pages/ModelEvaluation'
import CodeAnalyzer from './pages/CodeAnalyzer'
import Problems from './pages/Problems'
import ProblemPage from './pages/ProblemPage'
import Dashboard from './pages/Dashboard'
import SimilarQuestions from './pages/SimilarQuestions'
import TopicTracker from './pages/TopicTracker'
import Progress from './pages/Progress'
import Interview from './pages/Interview'
import Plan from './pages/Plan'
import Settings from './pages/Settings'
import CoachProvider from './components/CoachProvider'

const navItems = [
  { to: '/', label: 'Model Evaluation' },
  { to: '/problems', label: 'Problems' },
  { to: '/analyzer', label: 'Code Analyzer' },
  { to: '/interview', label: 'Mock Interview' },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/plan', label: 'Plan' },
  { to: '/similar', label: 'Similar Questions' },
  { to: '/topics', label: 'Topic Tracker' },
  { to: '/progress', label: 'Progress' },
  { to: '/settings', label: 'Settings' },
]

// Navbar + page container. Sirf logged-in pages is ke andar aate hain.
function Shell() {
  const { user, logout } = useAuth()
  return (
    <div className="min-h-screen bg-slate-50">
      <nav className="bg-slate-900 text-white px-6 py-4 flex gap-6 items-center flex-wrap">
        <span className="font-bold text-lg">🤖 AI Coding Coach</span>
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `text-sm ${isActive ? 'text-blue-400 font-semibold' : 'text-slate-300 hover:text-white'}`
            }
          >
            {item.label}
          </NavLink>
        ))}
        <div className="ml-auto flex items-center gap-3 text-sm text-slate-300">
          {user && <span>{user.name || user.email}</span>}
          {typeof logout === 'function' && (
            <button onClick={logout} className="text-slate-300 hover:text-white underline">
              Logout
            </button>
          )}
        </div>
      </nav>
      <CoachProvider>
        <main className="p-6 max-w-6xl mx-auto">
          <Outlet />
        </main>
      </CoachProvider>
    </div>
  )
}

function App() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />

      {/* Login zaroori: ProtectedRoute bina login ke /login par bhej deta hai */}
      <Route element={<ProtectedRoute />}>
        <Route element={<Shell />}>
          <Route path="/" element={<ModelEvaluation />} />
          <Route path="/problems" element={<Problems />} />
          <Route path="/problems/:id" element={<ProblemPage />} />
          <Route path="/analyzer" element={<CodeAnalyzer />} />
          <Route path="/interview" element={<Interview />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/similar" element={<SimilarQuestions />} />
          <Route path="/topics" element={<TopicTracker />} />
          <Route path="/progress" element={<Progress />} />
          <Route path="/plan" element={<Plan />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Route>
    </Routes>
  )
}

export default App