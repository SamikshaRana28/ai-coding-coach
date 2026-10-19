import { useEffect, useRef, useState } from 'react'
import { Routes, Route, NavLink, Link, Outlet, Navigate } from 'react-router-dom'
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
import Coach from './pages/Coach'
import Plan from './pages/Plan'
import Settings from './pages/Settings'
import CoachProvider from './components/CoachProvider'
import { PLAN_CHANGED_EVENT } from './components/coachContext'
import { getStreak } from './api'

// "Mock Interview" is no longer a top-level item: it lives in Coach > Interview Practice.
const navItems = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/problems', label: 'Problems' },
  { to: '/coach', label: 'Coach' },
  { to: '/plan', label: 'Plan' },
  { to: '/analyzer', label: 'Code Analyzer' },
  { to: '/similar', label: 'Similar Questions' },
  { to: '/topics', label: 'Topic Tracker' },
  { to: '/progress', label: 'Progress' },
  { to: '/model-evaluation', label: 'Model Evaluation' },
]

const linkClass = ({ isActive }) =>
  `text-sm rounded-md px-2 py-1 ${isActive ? 'text-slate-900 font-semibold bg-elevated' : 'text-slate-600 hover:text-slate-900'}`

function StreakFlame() {
  const [streak, setStreak] = useState(null)
  useEffect(() => {
    let cancelled = false
    const load = () => getStreak()
      .then((r) => { if (!cancelled) setStreak(r.data.current_streak ?? 0) })
      .catch(() => { /* optional */ })
    load()
    window.addEventListener(PLAN_CHANGED_EVENT, load)
    return () => { cancelled = true; window.removeEventListener(PLAN_CHANGED_EVENT, load) }
  }, [])
  if (streak === null) return null
  return (
    <Link to="/plan" title="Current streak" aria-label={`${streak} day streak`}
      className="flex items-center gap-1 text-sm text-orange-500 border border-line rounded-full px-3 py-1 hover:bg-elevated">
      <span aria-hidden="true">{streak > 0 ? '🔥' : '🕯️'}</span>{streak}
    </Link>
  )
}

function UserMenu() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey) }
  }, [open])

  const name = user?.name || user?.email || 'Account'
  return (
    <div className="relative" ref={ref}>
      <button type="button" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 text-sm border border-line rounded-full pl-1 pr-3 py-1 hover:bg-elevated">
        <span className="w-7 h-7 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-bold" aria-hidden="true">
          {name.trim().charAt(0).toUpperCase()}
        </span>
        <span className="max-w-[8rem] truncate hidden sm:inline">{name}</span>
      </button>
      {open && (
        <div role="menu" className="absolute right-0 mt-2 w-48 card shadow-glow p-1 z-50">
          <div className="px-3 py-2 text-xs text-slate-500 truncate border-b border-line">{user?.email}</div>
          <Link role="menuitem" to="/settings" onClick={() => setOpen(false)} className="block px-3 py-2 text-sm rounded-md hover:bg-elevated">⚙️ Settings</Link>
          {typeof logout === 'function' && (
            <button role="menuitem" type="button" onClick={logout} className="w-full text-left px-3 py-2 text-sm rounded-md hover:bg-elevated text-red-600">
              Log out
            </button>
          )}
        </div>
      )}
    </div>
  )
}

// Navbar + page container. Only logged-in pages live inside this.
function Shell() {
  const [drawer, setDrawer] = useState(false)

  useEffect(() => {
    if (!drawer) return undefined
    const onKey = (e) => { if (e.key === 'Escape') setDrawer(false) }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [drawer])

  return (
    <CoachProvider>
      <div className="min-h-screen bg-canvas">
        <header className="sticky top-0 z-30 bg-surface/95 backdrop-blur border-b border-line">
          <nav aria-label="Main" className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center gap-3">
            <button type="button" aria-label="Open menu" aria-expanded={drawer} onClick={() => setDrawer(true)}
              className="lg:hidden text-slate-700 text-xl px-2 py-1 rounded-md hover:bg-elevated">☰</button>
            <Link to="/dashboard" className="font-bold text-lg whitespace-nowrap">🤖 AI Coding Coach</Link>

            <div className="hidden lg:flex items-center gap-1 ml-4 flex-wrap">
              {navItems.map((item) => (
                <NavLink key={item.to} to={item.to} className={linkClass}>{item.label}</NavLink>
              ))}
            </div>

            <div className="ml-auto flex items-center gap-2">
              <StreakFlame />
              <UserMenu />
            </div>
          </nav>
        </header>

        {drawer && (
          <div className="lg:hidden fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label="Menu">
            <button type="button" aria-label="Close menu" className="absolute inset-0 bg-black/60" onClick={() => setDrawer(false)} />
            <div className="absolute left-0 top-0 bottom-0 w-72 max-w-[85vw] bg-surface border-r border-line p-4 flex flex-col gap-1 overflow-y-auto">
              <div className="flex items-center justify-between mb-3">
                <span className="font-bold">🤖 AI Coding Coach</span>
                <button type="button" aria-label="Close menu" onClick={() => setDrawer(false)} className="text-slate-500 px-2 py-1">✕</button>
              </div>
              {navItems.map((item) => (
                <NavLink key={item.to} to={item.to} onClick={() => setDrawer(false)}
                  className={({ isActive }) => `px-3 py-2.5 rounded-lg text-sm ${isActive ? 'bg-elevated text-slate-900 font-semibold' : 'text-slate-600 hover:bg-elevated'}`}>
                  {item.label}
                </NavLink>
              ))}
              <NavLink to="/settings" onClick={() => setDrawer(false)} className="px-3 py-2.5 rounded-lg text-sm text-slate-600 hover:bg-elevated">Settings</NavLink>
            </div>
          </div>
        )}

        <main className="p-4 sm:p-6 max-w-6xl mx-auto">
          <Outlet />
        </main>
      </div>
    </CoachProvider>
  )
}

function App() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />

      {/* Login required: ProtectedRoute sends you to /login otherwise */}
      <Route element={<ProtectedRoute />}>
        <Route element={<Shell />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/problems" element={<Problems />} />
          <Route path="/problems/:id" element={<ProblemPage />} />
          <Route path="/coach" element={<Coach />} />
          <Route path="/interview" element={<Navigate to="/coach?tab=interview" replace />} />
          <Route path="/plan" element={<Plan />} />
          <Route path="/analyzer" element={<CodeAnalyzer />} />
          <Route path="/similar" element={<SimilarQuestions />} />
          <Route path="/topics" element={<TopicTracker />} />
          <Route path="/progress" element={<Progress />} />
          <Route path="/model-evaluation" element={<ModelEvaluation />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Route>
    </Routes>
  )
}

export default App
