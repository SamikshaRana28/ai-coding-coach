
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const TOKEN_KEY = 'access_token'

export const AUTH_EXPIRED_EVENT = 'auth:expired'

export const getToken = () => localStorage.getItem(TOKEN_KEY)

export const setToken = (token) => {
  localStorage.setItem(TOKEN_KEY, token)
}

export const clearToken = () => {
  localStorage.removeItem(TOKEN_KEY)
}

export const api = axios.create({ baseURL: API_BASE })

api.interceptors.request.use((config) => {
  const token = getToken()

  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const url = error.config?.url || ''
    const isAuthRequest =
      url.includes('/auth/login') || url.includes('/auth/signup')

    if (status === 401 && !isAuthRequest && getToken()) {
      clearToken()
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))
    }

    return Promise.reject(error)
  },
)

// Authentication
export const getMe = () => api.get('/auth/me')
export const loginRequest = (data) => api.post('/auth/login', data)
export const signupRequest = (data) => api.post('/auth/signup', data)

// Existing ML APIs
export const getModelEvaluation = () => api.get('/model-evaluation')
export const getDatasetStats = () => api.get('/dataset-stats')
export const analyzeCode = (data) => api.post('/analyze', data)
export const predictWeakTopic = (data) => api.post('/predict', data)
export const predictDifficulty = (data) => api.post('/predict-difficulty', data)
export const getRecommendations = (data) => api.post('/recommend', data)
export const getScore = (data) => api.post('/score', data)
export const getProgress = (userId) => api.get(`/progress/${userId}`)

// Problems (the logged-in user comes from the JWT that the interceptor above adds)
export const listProblems = (params) => api.get('/problems', { params })
export const getProblem = (id) => api.get(`/problems/${id}`)
export const submitProblem = (id, data) => api.post(`/problems/${id}/submit`, data)
export const markProblemSolved = (id) => api.post(`/problems/${id}/mark-solved`)

// Hints (Part 4): POST with no `level` = "give me the next hint"; `code` is the unsaved editor text
export const requestHint = (id, data = {}) => api.post(`/problems/${id}/hint`, data)
export const getProblemStats = () => api.get('/problem-stats')

// Coach (the conversation is stored on the server, per logged-in user)
export const coachChat = (data) => api.post('/coach/chat', data)
export const getCoachHistory = (limit = 50) => api.get('/coach/history', { params: { limit } })
export const clearCoachHistory = () => api.delete('/coach/history')

// Study plan, daily tasks, streak (Part 5)
export const generatePlan = (data = {}) => api.post('/plan/generate', data)
export const getCurrentPlan = () => api.get('/plan/current')
export const getFocus = () => api.get('/plan/focus')
export const getTodayTasks = () => api.get('/tasks/today')
export const completeTask = (id) => api.post(`/tasks/${id}/complete`)
export const skipTask = (id) => api.post(`/tasks/${id}/skip`)
export const rescheduleTasks = () => api.post('/tasks/reschedule')
export const getStreak = () => api.get('/streak')

// Follow-ups: check-in, weekly review, notifications, settings (Part 6)
export const getCheckinToday = () => api.get('/coach/checkin/today')
export const saveCheckin = (data) => api.post('/coach/checkin', data)
export const getWeeklyReview = () => api.get('/plan/weekly-review')
export const startWeeklyReview = () => api.post('/plan/weekly-review')
export const confirmWeeklyReview = () => api.post('/plan/weekly-review/confirm')
export const discardWeeklyReview = () => api.delete('/plan/weekly-review')
export const getNotifications = (limit = 20) => api.get('/notifications', { params: { limit } })
export const markNotificationsRead = () => api.post('/notifications/read')
export const getSettings = () => api.get('/settings')
export const updateSettings = (data) => api.put('/settings', data)
// Interview agent
export const getInterviewTopics = () => api.get('/interview/topics')
export const extractResume = (file) => {            // PDF -> text (nothing is stored on the server)
  const form = new FormData()
  form.append('file', file)
  return api.post('/interview/resume/extract', form)
}
export const saveInterviewMetrics = (id, data) => api.post(`/interview/${id}/metrics`, data)   // aggregate numbers only
export const deleteInterviewResume = (id) => api.delete(`/interview/${id}/resume`)
export const startInterview = (data) => api.post('/interview/start', data)
export const sendAnswer = (id, data) => api.post(`/interview/${id}/answer`, data)
export const getInterview = (id) => api.get(`/interview/${id}`)
export const getScorecard = (id) => api.get(`/interview/${id}/scorecard`)
export const getWeakPatterns = (userId) => api.get(`/weak-patterns/${userId}`)

// FastAPI errors
export const errorMessage = (e) => {
  const detail = e?.response?.data?.detail

  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg).join('; ')
  }

  return detail || e?.message || 'Something went wrong'
}