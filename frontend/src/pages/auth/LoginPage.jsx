import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { authAPI } from '../../services/api'
import useAuthStore from '../../store/authStore'

export default function LoginPage() {
  const navigate = useNavigate()
  const login    = useAuthStore((s) => s.login)

  const [form, setForm]       = useState({ username: '', password: '' })
  const [error, setError]     = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const res = await authAPI.login(form)
      login(res.data.user, res.data.organizations, res.data.tokens)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.error || 'Erreur de connexion')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="w-full max-w-md">

        {/* Logo */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-primary">ProcessIntelligence</h1>
          <p className="text-secondary mt-2">Auditez et optimisez vos procédures</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-xl shadow-sm border border-light p-8">
          <h2 className="text-xl font-semibold text-primary mb-6">Connexion</h2>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-4 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-primary mb-1">
                Nom d'utilisateur
              </label>
              <input
                type="text"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                className="w-full border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary"
                placeholder="votre_username"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-primary mb-1">
                Mot de passe
              </label>
              <input
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                className="w-full border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary"
                placeholder="••••••••"
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-secondary text-white rounded-lg py-2 text-sm font-medium hover:bg-primary transition-colors disabled:opacity-50"
            >
              {loading ? 'Connexion...' : 'Se connecter'}
            </button>
          </form>

          <p className="text-center text-sm text-gray-500 mt-6">
            Pas encore de compte ?{' '}
            <Link to="/register" className="text-secondary hover:underline font-medium">
              Créer un compte
            </Link>
          </p>
        </div>

        {/* Diagnostic Express */}
        <div className="text-center mt-6">
          <p className="text-sm text-gray-500">
            Vous voulez tester sans compte ?
          </p>
          <Link
            to="/diagnostic"
            className="text-secondary text-sm font-medium hover:underline"
          >
            Diagnostic Express →
          </Link>
        </div>

      </div>
    </div>
  )
}