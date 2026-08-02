import {
  createContext, useContext, useState, useCallback, useEffect, ReactNode,
} from 'react'
import { api } from './api'

// ===== Types =====
export interface AuthUser {
  user_id: string
  name: string
  email: string
  role: 'user' | 'admin' | 'operator'
  status: 'active' | 'disabled'
}

interface AuthState {
  user: AuthUser | null
  token: string | null
  loading: boolean
  isAuthenticated: boolean
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name?: string) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
}

// ===== Constants =====
const TOKEN_KEY = 'vt_access_token'
const USER_KEY = 'vt_user'

// ===== Context =====
const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

// ===== Provider =====
export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    token: null,
    loading: true,
    isAuthenticated: false,
  })

  // Initialize from localStorage on mount
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY)
    const userStr = localStorage.getItem(USER_KEY)

    if (token && userStr) {
      try {
        const user = JSON.parse(userStr) as AuthUser
        setState({ user, token, loading: false, isAuthenticated: true })

        // Validate token in background
        api<AuthUser>('GET', '/auth/me')
          .then((freshUser) => {
            localStorage.setItem(USER_KEY, JSON.stringify(freshUser))
            setState((prev) => ({ ...prev, user: freshUser }))
          })
          .catch(() => {
            // Token invalid or expired
            localStorage.removeItem(TOKEN_KEY)
            localStorage.removeItem(USER_KEY)
            setState({ user: null, token: null, loading: false, isAuthenticated: false })
          })
      } catch {
        localStorage.removeItem(TOKEN_KEY)
        localStorage.removeItem(USER_KEY)
        setState({ user: null, token: null, loading: false, isAuthenticated: false })
      }
    } else {
      setState({ user: null, token: null, loading: false, isAuthenticated: false })
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const res = await api<{ access_token: string; user: AuthUser }>(
      'POST', '/auth/login', { email, password },
    )
    localStorage.setItem(TOKEN_KEY, res.access_token)
    localStorage.setItem(USER_KEY, JSON.stringify(res.user))
    setState({ user: res.user, token: res.access_token, loading: false, isAuthenticated: true })
  }, [])

  const register = useCallback(async (email: string, password: string, name?: string) => {
    const res = await api<{ access_token: string; user: AuthUser }>(
      'POST', '/auth/register', { email, password, name: name || '' },
    )
    localStorage.setItem(TOKEN_KEY, res.access_token)
    localStorage.setItem(USER_KEY, JSON.stringify(res.user))
    setState({ user: res.user, token: res.access_token, loading: false, isAuthenticated: true })
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setState({ user: null, token: null, loading: false, isAuthenticated: false })
  }, [])

  const refreshUser = useCallback(async () => {
    if (!state.token) return
    try {
      const freshUser = await api<AuthUser>('GET', '/auth/me')
      localStorage.setItem(USER_KEY, JSON.stringify(freshUser))
      setState((prev) => ({ ...prev, user: freshUser }))
    } catch {
      // ignore
    }
  }, [state.token])

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  )
}

// ===== Token getter (for api.ts to use) =====
export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}
