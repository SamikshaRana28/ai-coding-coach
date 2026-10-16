
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

// Problems
export const CURRENT_USER_ID = 1
const userHeaders = { 'X-User-Id': String(CURRENT_USER_ID) }

export const listProblems = (params) =>
  api.get('/problems', { params, headers: userHeaders })

export const getProblem = (id) =>
  api.get(`/problems/${id}`, { headers: userHeaders })

export const submitProblem = (id, data) =>
  api.post(`/problems/${id}/submit`, data, { headers: userHeaders })

export const markProblemSolved = (id) =>
  api.post(`/problems/${id}/mark-solved`, null, { headers: userHeaders })

// FastAPI errors
export const errorMessage = (e) => {
  const detail = e?.response?.data?.detail

  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg).join('; ')
  }

  return detail || e?.message || 'Something went wrong'
}