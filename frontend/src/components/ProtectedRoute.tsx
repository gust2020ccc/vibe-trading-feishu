import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../lib/auth'

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuth()
  const location = useLocation()

  // Show loading while checking auth state
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-bg">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-border border-t-accent rounded-full animate-spin" />
          <span className="text-sm text-slate-500">正在验证身份...</span>
        </div>
      </div>
    )
  }

  // Not authenticated — redirect to login with return URL
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return <>{children}</>
}
