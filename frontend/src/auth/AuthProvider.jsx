import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AUTH_EXPIRED_EVENT,
  clearToken,
  getMe,
  getToken,
  loginRequest,
  setToken,
  signupRequest,
} from '../api'
import { AuthContext } from './authContext'

export default function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  // If there is a stored token we must validate it (GET /auth/me) before deciding
  // whether to show the app or the login page, so start in "loading".
  const [loading, setLoading] = useState(() => Boolean(getToken()))
  const [bootError, setBootError] = useState(null)

  const loadUser = useCallback(async () => {
    try {
      const res = await getMe()
      setUser(res.data)
    } catch (e) {
      if (e.response?.status === 401) {
        clearToken()
        setUser(null)
      } else {
        // Server asleep / network down: keep the token, let the user retry.
        setBootError('Could not reach the server. It may be waking up - please retry in a few seconds.')
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (getToken()) loadUser()
  }, [loadUser])

  // The axios 401 interceptor fires this when a token stops being valid.
  useEffect(() => {
    const onExpired = () => setUser(null)
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired)
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired)
  }, [])

  const retry = useCallback(() => {
    setBootError(null)
    setLoading(true)
    loadUser()
  }, [loadUser])

  const login = useCallback(async (email, password) => {
    const res = await loginRequest({ email, password })
    setToken(res.data.access_token)
    setUser(res.data.user)
    setBootError(null)
    return res.data.user
  }, [])

  const signup = useCallback(async ({ firstName, lastName, email, password }) => {
    const res = await signupRequest({
      email,
      password,
      first_name: firstName,
      last_name: lastName,
      name: `${firstName} ${lastName}`.trim(),
    })
    setToken(res.data.access_token)
    setUser(res.data.user)
    setBootError(null)
    return res.data.user
  }, [])

  const logout = useCallback(() => {
    clearToken()
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, loading, bootError, retry, login, signup, logout }),
    [user, loading, bootError, retry, login, signup, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
