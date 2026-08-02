const BASE = ''

// ===== Core fetch with auth =====
export async function api<T = any>(method: string, path: string, body?: any): Promise<T> {
  const opts: RequestInit = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }

  // Attach JWT token if available
  const token = localStorage.getItem('vt_access_token')
  if (token) {
    opts.headers = { ...opts.headers, Authorization: `Bearer ${token}` }
  }

  if (body) opts.body = JSON.stringify(body)

  const res = await fetch(BASE + path, opts)

  // Handle 401: token expired or invalid
  if (res.status === 401) {
    localStorage.removeItem('vt_access_token')
    localStorage.removeItem('vt_user')
    // Redirect to login if not already there
    if (!window.location.pathname.startsWith('/login') && !window.location.pathname.startsWith('/register')) {
      window.location.href = '/login'
    }
  }

  if (!res.ok) {
    let msg = res.statusText
    try {
      const err = await res.json()
      msg = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail || err)
    } catch {}
    throw new Error(msg)
  }
  return res.json()
}

// ===== Auth APIs =====
export const authApi = {
  login: (email: string, password: string) =>
    api<{ access_token: string; user: any }>('POST', '/auth/login', { email, password }),
  register: (email: string, password: string, name?: string) =>
    api<{ access_token: string; user: any }>('POST', '/auth/register', { email, password, name: name || '' }),
  me: () => api<any>('GET', '/auth/me'),
  refresh: () => api<{ access_token: string; user: any }>('POST', '/auth/refresh'),
  changePassword: (oldPassword: string, newPassword: string) =>
    api('POST', '/auth/change-password', { old_password: oldPassword, new_password: newPassword }),
}

// Strategy APIs
export const strategyApi = {
  list: (params?: Record<string, string>) => {
    const qs = new URLSearchParams(params).toString()
    return api('GET', `/strategies${qs ? '?' + qs : ''}`)
  },
  get: (id: string, includeCode = false) =>
    api('GET', `/strategies/${id}?include_code=${includeCode}`),
  create: (data: any) => api('POST', '/strategies', data),
  update: (id: string, data: any) => api('PUT', `/strategies/${id}`, data),
  delete: (id: string) => api('DELETE', `/strategies/${id}`),
  versions: (id: string) => api('GET', `/strategies/${id}/versions`),
  rollback: (id: string, ver: number) => api('POST', `/strategies/${id}/rollback/${ver}`),
  publish: (id: string) => api('POST', `/strategies/${id}/publish`),
  archive: (id: string) => api('POST', `/strategies/${id}/archive`),
  clone: (id: string) => api('POST', `/strategies/${id}/clone`),
  subscribe: (id: string) => api('POST', `/strategies/${id}/subscribe`),
  unsubscribe: (id: string) => api('DELETE', `/strategies/${id}/subscribe`),
  rate: (id: string, rating: number) => api('POST', `/strategies/${id}/rate`, { rating }),
  templates: () => api('GET', '/strategies/templates'),
  nlGenerate: (description: string, name?: string, autoCreate = true) =>
    api('POST', '/strategies/nl-generate', { description, name, auto_create: autoCreate }),
}

// Factor APIs
export const factorApi = {
  list: (params?: Record<string, string>) => {
    const qs = new URLSearchParams(params).toString()
    return api('GET', `/factors${qs ? '?' + qs : ''}`)
  },
  get: (id: string) => api('GET', `/factors/${id}`),
  create: (data: any) => api('POST', '/factors', data),
  update: (id: string, data: any) => api('PUT', `/factors/${id}`, data),
  delete: (id: string) => api('DELETE', `/factors/${id}`),
  portfolios: () => api('GET', '/factors/portfolios'),
  createPortfolio: (data: any) => api('POST', '/factors/portfolios', data),
  deletePortfolio: (id: string) => api('DELETE', `/factors/portfolios/${id}`),
}

// Backtest APIs
export const backtestApi = {
  strategies: () => api('GET', '/backtest/strategies'),
  strategy: (id: string) => api('GET', `/backtest/strategies/${id}`),
  run: (data: any) => api('POST', '/backtest/run', data),
  runs: (limit = 20) => api('GET', `/backtest/runs?limit=${limit}`),
  chart: (runId: string) => `/backtest/runs/${runId}/chart`,
  nlRun: (description: string) => api('POST', '/backtest/custom', { description }),
}

// Marketplace APIs
export const marketApi = {
  strategies: (params?: Record<string, string>) => {
    const qs = new URLSearchParams(params).toString()
    return api('GET', `/marketplace/strategies${qs ? '?' + qs : ''}`)
  },
  factors: (params?: Record<string, string>) => {
    const qs = new URLSearchParams(params).toString()
    return api('GET', `/marketplace/factors${qs ? '?' + qs : ''}`)
  },
  featuredStrategies: () => api('GET', '/marketplace/strategies/featured'),
  featuredFactors: () => api('GET', '/marketplace/factors/featured'),
  stats: () => api('GET', '/marketplace/stats'),
}

// Admin APIs
export const adminApi = {
  users: () => api('GET', '/admin/users'),
  user: (id: string) => api('GET', `/admin/users/${id}`),
  createUser: (data: any) => api('POST', '/admin/users', data),
  updateUser: (id: string, data: any) => api('PUT', `/admin/users/${id}`, data),
  deleteUser: (id: string) => api('DELETE', `/admin/users/${id}`),
  quota: (id: string) => api('GET', `/admin/users/${id}/quota`),
  updateQuota: (id: string, data: any) => api('PUT', `/admin/users/${id}/quota`, data),
  usageSummary: () => api('GET', '/admin/usage/summary'),
  dailyUsage: (from?: string, to?: string) =>
    api('GET', `/admin/usage/daily${from ? '?date_from=' + from : ''}${to ? '&date_to=' + to : ''}`),
}

// Settings APIs
export const settingsApi = {
  llm: () => api('GET', '/settings/llm'),
  updateLlm: (data: any) => api('PUT', '/settings/llm', data),
  dataSources: () => api('GET', '/settings/data-sources'),
  updateDataSources: (data: any) => api('PUT', '/settings/data-sources', data),
}

// System APIs
export const systemApi = {
  ready: () => api('GET', '/ready'),
  skills: () => api('GET', '/skills'),
}
