import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Zap, Mail, Lock, User, Eye, EyeOff, ArrowRight, Check, ShieldCheck } from 'lucide-react'
import { useAuth } from '../lib/auth'
import { authApi } from '../lib/api'

export default function Register() {
  const navigate = useNavigate()
  const { register } = useAuth()

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [needsSetup, setNeedsSetup] = useState(false)

  const pwChecks = {
    length: password.length >= 6,
    match: password === confirmPw && confirmPw.length > 0,
  }

  const canSubmit = pwChecks.length && pwChecks.match && email.includes('@')

  // Check if this will be the first admin
  useEffect(() => {
    authApi.setupStatus()
      .then((res) => {
        if (res.needs_setup) {
          setNeedsSetup(true)
        }
      })
      .catch(() => {
        // Ignore
      })
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!canSubmit) return
    setLoading(true)
    try {
      const result = await register(email, password, name || undefined)
      // If first admin, show a brief success state before navigating
      if (result?.is_first_admin) {
        // Short delay so user sees they're now admin, then navigate
        setTimeout(() => navigate('/', { replace: true }), 100)
      } else {
        navigate('/', { replace: true })
      }
    } catch (err: any) {
      setError(err.message || '注册失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg px-4 py-8">
      {/* Background decoration */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-accent/5 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-cyan-500/5 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-accent to-cyan-500 flex items-center justify-center glow">
              <Zap className="w-6 h-6 text-white" />
            </div>
            <span className="text-2xl font-bold gradient-text">Vibe Trading</span>
          </div>
          <p className="text-sm text-slate-500">创建您的账户，开始量化之旅</p>
        </div>

        {/* Card */}
        <div className="bg-surface border border-border rounded-2xl p-8 shadow-xl">
          <h1 className="text-lg font-semibold text-slate-100 mb-1">注册</h1>
          <p className="text-xs text-slate-500 mb-6">填写以下信息创建新账户</p>

          {/* First admin banner */}
          {needsSetup && (
            <div className="mb-4 px-4 py-3 rounded-lg bg-accent/10 border border-accent/20 text-accent text-xs space-y-1">
              <div className="flex items-start gap-2">
                <ShieldCheck className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-slate-200">系统初始化</p>
                  <p className="text-slate-400 mt-0.5">您将成为首位注册用户，自动获得<strong className="text-accent">系统管理员</strong>权限，可管理所有用户和系统配置。</p>
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="mb-4 px-3 py-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Name */}
            <div>
              <label className="block text-xs text-slate-400 mb-1.5 font-medium">用户名（可选）</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600" />
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="您的昵称"
                  className="w-full pl-10 pr-3 py-2.5 bg-bg border border-border rounded-lg text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-accent transition-colors"
                />
              </div>
            </div>

            {/* Email */}
            <div>
              <label className="block text-xs text-slate-400 mb-1.5 font-medium">邮箱</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full pl-10 pr-3 py-2.5 bg-bg border border-border rounded-lg text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-accent transition-colors"
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label className="block text-xs text-slate-400 mb-1.5 font-medium">密码</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600" />
                <input
                  type={showPw ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="至少 6 个字符"
                  className="w-full pl-10 pr-10 py-2.5 bg-bg border border-border rounded-lg text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-accent transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-600 hover:text-slate-400"
                >
                  {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {/* Password hints */}
              <div className="flex gap-3 mt-2">
                <span className={`text-xs flex items-center gap-1 ${pwChecks.length ? 'text-green-400' : 'text-slate-600'}`}>
                  <Check className="w-3 h-3" /> 至少 6 位
                </span>
                <span className={`text-xs flex items-center gap-1 ${pwChecks.match ? 'text-green-400' : 'text-slate-600'}`}>
                  <Check className="w-3 h-3" /> 密码一致
                </span>
              </div>
            </div>

            {/* Confirm Password */}
            <div>
              <label className="block text-xs text-slate-400 mb-1.5 font-medium">确认密码</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600" />
                <input
                  type={showPw ? 'text' : 'password'}
                  required
                  value={confirmPw}
                  onChange={(e) => setConfirmPw(e.target.value)}
                  placeholder="再次输入密码"
                  className={`w-full pl-10 pr-3 py-2.5 bg-bg border rounded-lg text-sm text-slate-200 placeholder-slate-600 focus:outline-none transition-colors ${
                    confirmPw && !pwChecks.match ? 'border-red-500/50' : 'border-border focus:border-accent'
                  }`}
                />
              </div>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading || !canSubmit}
              className="w-full flex items-center justify-center gap-2 py-2.5 bg-accent hover:bg-accent-light text-white rounded-lg text-sm font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  {needsSetup ? '创建管理员账户' : '创建账户'}
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Login link */}
          <div className="mt-6 text-center text-xs text-slate-500">
            已有账号？
            <Link to="/login" className="text-accent hover:text-accent-light ml-1 font-medium">
              返回登录
            </Link>
          </div>
        </div>

        <p className="text-center text-xs text-slate-600 mt-6">
          © 2026 Vibe Trading · AI Native Quant Platform
        </p>
      </div>
    </div>
  )
}
