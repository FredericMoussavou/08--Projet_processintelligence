import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { authAPI } from '../../services/api'
import useAuthStore from '../../store/authStore'

const SECTORS = [
  { value: 'finance',   label: 'Finance / Banque' },
  { value: 'insurance', label: 'Assurance' },
  { value: 'health',    label: 'Santé / Médical' },
  { value: 'hr',        label: 'RH / Travail' },
  { value: 'food',      label: 'Agroalimentaire' },
  { value: 'other',     label: 'Autre' },
]

export default function RegisterPage() {
  const navigate = useNavigate()
  const login    = useAuthStore((s) => s.login)

  const [form, setForm] = useState({
    username         : '',
    email            : '',
    password         : '',
    organization_name: '',
    sector           : 'other',
  })
  const [error, setError]     = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const res = await authAPI.register(form)
      login(res.data.user, [res.data.organization], res.data.tokens)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.error || 'Erreur lors de la création du compte')
    } finally {
      setLoading(false)
    }
  }

  const update = (field) => (e) => setForm({ ...form, [field]: e.target.value })

  return (
    <div className="min-h-screen flex items-center justify-center bg-background py-8">
      <div className="w-full max-w-md">

        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-primary">ProcessIntelligence</h1>
          <p className="text-secondary mt-2">Créez votre compte</p>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-light p-8">
          <h2 className="text-xl font-semibold text-primary mb-6">Inscription</h2>

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
                onChange={update('username')}
                className="w-full border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-primary mb-1">
                Email
              </label>
              <input
                type="email"
                value={form.email}
                onChange={update('email')}
                className="w-full border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary"
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
                onChange={update('password')}
                className="w-full border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary"
                placeholder="8 caractères minimum"
                required
              />
            </div>

            <div className="border-t border-light pt-4">
              <p className="text-xs font-medium text-gray-400 uppercase mb-3">
                Votre organisation
              </p>

              <div className="space-y-3">
                <div>
                  <label className="block text-sm font-medium text-primary mb-1">
                    Nom de l'organisation
                  </label>
                  <input
                    type="text"
                    value={form.organization_name}
                    onChange={update('organization_name')}
                    className="w-full border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary"
                    placeholder="Mon Entreprise"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-primary mb-1">
                    Secteur d'activité
                  </label>
                  <select
                    value={form.sector}
                    onChange={update('sector')}
                    className="w-full border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary bg-white"
                  >
                    {SECTORS.map((s) => (
                      <option key={s.value} value={s.value}>{s.label}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-secondary text-white rounded-lg py-2 text-sm font-medium hover:bg-primary transition-colors disabled:opacity-50"
            >
              {loading ? 'Création...' : 'Créer mon compte'}
            </button>
          </form>

          <p className="text-center text-sm text-gray-500 mt-6">
            Déjà un compte ?{' '}
            <Link to="/login" className="text-secondary hover:underline font-medium">
              Se connecter
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}