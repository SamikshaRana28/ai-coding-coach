import axios from 'axios'

const API_BASE =
  'https://redesigned-fortnight-g4p59r69rrj5297x9-8000.app.github.dev'

export const api = axios.create({ baseURL: API_BASE })

export const getModelEvaluation = () => api.get('/model-evaluation')
export const getDatasetStats = () => api.get('/dataset-stats')
export const analyzeCode = (data) => api.post('/analyze', data)
export const predictWeakTopic = (data) => api.post('/predict', data)
export const predictDifficulty = (data) => api.post('/predict-difficulty', data)
export const getRecommendations = (data) => api.post('/recommend', data)
export const getScore = (data) => api.post('/score', data)
export const getProgress = (userId) => api.get(`/progress/${userId}`)