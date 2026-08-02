import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Strategies from './pages/Strategies'
import Factors from './pages/Factors'
import Backtest from './pages/Backtest'
import Marketplace from './pages/Marketplace'
import AIGenerate from './pages/AIGenerate'
import Admin from './pages/Admin'
import Settings from './pages/Settings'

export default function App() {
  return (
    <Routes>
      {/* Public auth routes */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* Protected app routes */}
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="strategies" element={<Strategies />} />
        <Route path="factors" element={<Factors />} />
        <Route path="backtest" element={<Backtest />} />
        <Route path="marketplace" element={<Marketplace />} />
        <Route path="ai-generate" element={<AIGenerate />} />
        <Route path="admin" element={<Admin />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Route>
    </Routes>
  )
}
