import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// ── Token storage (localStorage is fine for this project) ───────────────────
export const TOKEN_KEY = 'acc_token'
export const AUTH_EXPIRED_EVENT = 'auth:expired'

export const getToken = () => {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}
export const setToken = (token) => {
  try { localStorage.setItem(TOKEN_KEY, token) } catch { /* storage unavailable */ }
}
export const clearToken = () => {
  try { localStorage.removeItem(TOKEN_KEY) } catch { /* storage unavailable */ }
}

export const api = axios.create({ baseURL: API_BASE })

// Attach the Bearer token to every request.
api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// A 401 on a normal request means the session expired / token is invalid:
// drop the token and tell AuthProvider, which sends the user to /login.
// (A 401 from /auth/login itself just means "wrong password" - not a session expiry.)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = error.config?.url || ''
    const isAuthAttempt = url.startsWith('/auth/login') || url.startsWith('/auth/signup')
    if (error.response?.status === 401 && !isAuthAttempt && getToken()) {
      clearToken()
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))
    }
    return Promise.reject(error)
  },
)

// ── Auth ─────────────────────────────────────────────────────────────────────
export const loginRequest = (data) => api.post('/auth/login', data)
export const signupRequest = (data) => api.post('/auth/signup', data)
export const getMe = () => api.get('/auth/me')

// ── Existing endpoints (unchanged) ──────────────────────────────────────────
export const getModelEvaluation = () => api.get('/model-evaluation')
export const getDatasetStats = () => api.get('/dataset-stats')
export const analyzeCode = (data) => api.post('/analyze', data)
export const predictWeakTopic = (data) => api.post('/predict', data)
export const predictDifficulty = (data) => api.post('/predict-difficulty', data)
export const getRecommendations = (data) => api.post('/recommend', data)
export const getScore = (data) => api.post('/score', data)
export const getProgress = (userId) => api.get(`/progress/${userId}`)

// Interview agent
export const getInterviewTopics = () => api.get('/interview/topics')
export const startInterview = (data) => api.post('/interview/start', data)
export const sendAnswer = (id, data) => api.post(`/interview/${id}/answer`, data)
export const getInterview = (id) => api.get(`/interview/${id}`)
export const getScorecard = (id) => api.get(`/interview/${id}/scorecard`)
export const getWeakPatterns = (userId) => api.get(`/weak-patterns/${userId}`)
