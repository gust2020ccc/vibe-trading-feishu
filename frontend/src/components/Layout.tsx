import { useState, useCallback, useRef, useEffect } from 'react'
import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, CandlestickChart, FlaskConical, Beaker,
  Store, Bot, Users, Settings, Zap, Menu, X, LogOut, ChevronDown, UserCircle,
} from 'lucide-react'
import { useAuth } from '../lib/auth'

const navGroups = [
  {
    label: '工作区',
    items: [
      { to: '/', icon: LayoutDashboard, label: '仪表盘' },
      { to: '/strategies', icon: CandlestickChart, label: '策略管理' },
      { to: '/factors', icon: FlaskConical, label: '因子管理' },
      { to: '/backtest', icon: Beaker, label: '回测中心' },
    ],
  },
  {
    label: '发现',
    items: [
      { to: '/marketplace', icon: Store, label: '策略市场' },
      { to: '/ai-generate', icon: Bot, label: 'AI 生成' },
    ],
  },
  {
    label: '管理',
    items: [
      { to: '/admin', icon: Users, label: '用户管理' },
      { to: '/settings', icon: Settings, label: '系统设置' },
    ],
  },
]

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const menuRef = useRef<HTMLDivElement>(null)

  const closeSidebar = useCallback(() => setSidebarOpen(false), [])

  // Close user menu on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const initials = (user?.name || user?.email || 'U').slice(0, 2).toUpperCase()

  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/60 md:hidden"
          onClick={closeSidebar}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed md:static z-40 w-60 h-full bg-surface border-r border-border flex flex-col transition-transform duration-200 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        {/* Logo */}
        <div className="flex items-center gap-2 px-5 py-4 border-b border-border">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-cyan-500 flex items-center justify-center glow">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <span className="text-lg font-bold gradient-text">Vibe Trading</span>
          <button
            className="ml-auto md:hidden text-slate-400 hover:text-white"
            onClick={closeSidebar}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto p-3 space-y-1">
          {navGroups.map((group) => (
            <div key={group.label}>
              <div className="px-3 pt-4 pb-1 text-xs uppercase tracking-wider text-slate-500">
                {group.label}
              </div>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  onClick={closeSidebar}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all ${
                      isActive
                        ? 'bg-accent/15 text-accent-light font-medium'
                        : 'text-slate-400 hover:bg-surface2 hover:text-slate-200'
                    }`
                  }
                >
                  <item.icon className="w-4 h-4 flex-shrink-0" />
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-border text-xs text-slate-600">
          v1.0 · AI Native 量化平台
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex items-center gap-3 px-6 py-3 bg-surface border-b border-border">
          <button
            className="md:hidden text-slate-400 hover:text-white"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="w-5 h-5" />
          </button>
          <h1 className="text-sm font-medium text-slate-300 flex-1">
            {getPageTitle(location.pathname)}
          </h1>

          {/* User menu */}
          <div ref={menuRef} className="relative">
            <button
              onClick={() => setUserMenuOpen(!userMenuOpen)}
              className="flex items-center gap-2 px-2 py-1 rounded-lg hover:bg-surface2 transition-colors"
            >
              <div className="w-7 h-7 rounded-full bg-gradient-to-br from-accent to-cyan-500 flex items-center justify-center text-xs font-semibold text-white">
                {initials}
              </div>
              <span className="text-sm text-slate-300 hidden sm:block">
                {user?.name || user?.email}
              </span>
              <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
            </button>

            {/* Dropdown */}
            {userMenuOpen && (
              <div className="absolute right-0 top-full mt-1 w-56 bg-surface border border-border rounded-xl shadow-xl py-1 z-50 animate-in">
                {/* User info */}
                <div className="px-3 py-2 border-b border-border">
                  <div className="flex items-center gap-2">
                    <UserCircle className="w-4 h-4 text-slate-500" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-slate-200 truncate">{user?.name || '用户'}</p>
                      <p className="text-xs text-slate-500 truncate">{user?.email}</p>
                    </div>
                  </div>
                  <div className="mt-1.5 flex items-center gap-1.5">
                    <span className="text-xs px-1.5 py-0.5 rounded bg-accent/15 text-accent-light">
                      {user?.role === 'admin' ? '管理员' : user?.role === 'operator' ? '运营' : '用户'}
                    </span>
                  </div>
                </div>

                {/* Menu items */}
                <button
                  onClick={() => { setUserMenuOpen(false); navigate('/settings') }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-300 hover:bg-surface2 transition-colors"
                >
                  <Settings className="w-4 h-4 text-slate-500" />
                  系统设置
                </button>
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  退出登录
                </button>
              </div>
            )}
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function getPageTitle(path: string): string {
  const titles: Record<string, string> = {
    '/': '仪表盘',
    '/strategies': '策略管理',
    '/factors': '因子管理',
    '/backtest': '回测中心',
    '/marketplace': '策略市场',
    '/ai-generate': 'AI 生成策略',
    '/admin': '用户管理',
    '/settings': '系统设置',
  }
  return titles[path] || 'Vibe Trading'
}
