import { useState, useCallback, createContext, useContext, ReactNode } from 'react'
import { CheckCircle, XCircle, Info, X } from 'lucide-react'

// ===== Toast =====
interface Toast { id: number; message: string; type: 'success' | 'error' | 'info' }
const ToastContext = createContext<(msg: string, type?: Toast['type']) => void>(() => {})
export const useToast = () => useContext(ToastContext)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const showToast = useCallback((message: string, type: Toast['type'] = 'info') => {
    const id = Date.now() + Math.random()
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 3500)
  }, [])

  return (
    <ToastContext.Provider value={showToast}>
      {children}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg shadow-lg text-sm text-white animate-slide-in ${
              t.type === 'success' ? 'bg-green-500' : t.type === 'error' ? 'bg-red-500' : 'bg-accent'
            }`}
          >
            {t.type === 'success' && <CheckCircle className="w-4 h-4" />}
            {t.type === 'error' && <XCircle className="w-4 h-4" />}
            {t.type === 'info' && <Info className="w-4 h-4" />}
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

// ===== Card =====
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`bg-surface border border-border rounded-xl ${className}`}>
      {children}
    </div>
  )
}

export function CardHeader({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="flex items-center justify-between px-5 py-3 border-b border-border">
      <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
      {action}
    </div>
  )
}

// ===== Button =====
export function Button({
  children, variant = 'primary', size = 'md', className = '', ...props
}: {
  children: ReactNode
  variant?: 'primary' | 'ghost' | 'green' | 'red'
  size?: 'sm' | 'md'
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const variants = {
    primary: 'bg-accent hover:bg-accent-light text-white',
    ghost: 'bg-transparent border border-border text-slate-400 hover:bg-surface2 hover:text-slate-200',
    green: 'bg-green-500 hover:bg-green-600 text-white',
    red: 'bg-red-500 hover:bg-red-600 text-white',
  }
  const sizes = { sm: 'px-2.5 py-1 text-xs', md: 'px-3.5 py-1.5 text-sm' }
  return (
    <button
      className={`rounded-lg font-medium transition-all ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}

// ===== Badge =====
export function Badge({ children, color = 'gray' }: { children: ReactNode; color?: 'gray' | 'green' | 'blue' | 'orange' | 'red' }) {
  const colors = {
    gray: 'bg-surface3 text-slate-400',
    green: 'bg-green-500/10 text-green-400',
    blue: 'bg-accent/15 text-accent-light',
    orange: 'bg-orange-500/10 text-orange-400',
    red: 'bg-red-500/10 text-red-400',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${colors[color]}`}>
      {children}
    </span>
  )
}

// ===== Modal =====
export function Modal({
  title, children, onClose, footer, maxWidth = 'max-w-2xl',
}: {
  title: string
  children: ReactNode
  onClose: () => void
  footer?: ReactNode
  maxWidth?: string
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 backdrop-blur-sm" onClick={onClose}>
      <div
        className={`bg-surface border border-border rounded-2xl w-[92%] ${maxWidth} max-h-[88vh] flex flex-col shadow-2xl`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center px-5 py-3.5 border-b border-border">
          <span className="text-base font-semibold flex-1">{title}</span>
          <button onClick={onClose} className="text-slate-500 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">{children}</div>
        {footer && <div className="flex gap-2 justify-end px-5 py-3 border-t border-border">{footer}</div>}
      </div>
    </div>
  )
}

// ===== Input =====
export function Input({ label, className = '', ...props }: { label?: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div>
      {label && <label className="block text-xs text-slate-400 mb-1.5 font-medium">{label}</label>}
      <input
        className={`w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-accent ${className}`}
        {...props}
      />
    </div>
  )
}

export function Textarea({ label, className = '', ...props }: { label?: string } & React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <div>
      {label && <label className="block text-xs text-slate-400 mb-1.5 font-medium">{label}</label>}
      <textarea
        className={`w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-accent resize-vertical ${className}`}
        {...props}
      />
    </div>
  )
}

export function Select({ label, children, className = '', ...props }: { label?: string; children: ReactNode } & React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div>
      {label && <label className="block text-xs text-slate-400 mb-1.5 font-medium">{label}</label>}
      <select
        className={`w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-slate-200 focus:outline-none focus:border-accent ${className}`}
        {...props}
      >
        {children}
      </select>
    </div>
  )
}

// ===== Empty State =====
export function EmptyState({ icon, title, subtitle }: { icon: ReactNode; title: string; subtitle?: string }) {
  return (
    <div className="text-center py-16 text-slate-500">
      <div className="flex justify-center mb-3 text-slate-600">{icon}</div>
      <p className="text-sm">{title}</p>
      {subtitle && <p className="text-xs mt-1 text-slate-600">{subtitle}</p>}
    </div>
  )
}

// ===== Loading =====
export function Loading({ text = '加载中...' }: { text?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-slate-500">
      <div className="w-4 h-4 border-2 border-border border-t-accent rounded-full animate-spin" />
      <span className="text-sm">{text}</span>
    </div>
  )
}

// ===== Stars =====
export function Stars({ avg, count }: { avg: number; count?: number }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className="text-orange-400 text-sm">
        {'★'.repeat(Math.round(avg))}
        <span className="text-slate-700">{'★'.repeat(5 - Math.round(avg))}</span>
      </span>
      {count !== undefined && <span className="text-xs text-slate-500">{avg.toFixed(1)} ({count})</span>}
    </span>
  )
}

// ===== Helpers =====
export function fmtDate(s?: string): string {
  if (!s) return ''
  try {
    return new Date(s).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return s
  }
}

export function fmtNum(n?: number): string {
  if (n === undefined || n === null) return '-'
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1) + 'M'
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + 'K'
  return n.toFixed(2)
}

export function fmtPct(n?: number): string {
  if (n === undefined || n === null) return '-'
  return (n * 100).toFixed(2) + '%'
}
