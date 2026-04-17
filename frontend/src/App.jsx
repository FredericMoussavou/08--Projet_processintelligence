import { Routes, Route, Navigate } from 'react-router-dom'
import useAuthStore from './store/authStore'
import LoginPage from './pages/auth/LoginPage'
import RegisterPage from './pages/auth/RegisterPage'
import DashboardLayout from './components/layout/DashboardLayout'
import DashboardHome from './pages/dashboard/DashboardHome'
import ProceduresList from './pages/procedures/ProceduresList'
import ProcedureDetail from './pages/procedures/ProcedureDetail'
import IngestPage from './pages/procedures/IngestPage'

// Route protégée
function PrivateRoute({ children }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  return isAuthenticated ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      {/* Routes publiques */}
      <Route path="/login"    element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* Routes protégées */}
      <Route path="/" element={
        <PrivateRoute>
          <DashboardLayout />
        </PrivateRoute>
      }>
        <Route index                    element={<DashboardHome />} />
        <Route path="procedures"        element={<ProceduresList />} />
        <Route path="procedures/:id"    element={<ProcedureDetail />} />
        <Route path="procedures/ingest" element={<IngestPage />} />
      </Route>

      {/* Redirect */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}