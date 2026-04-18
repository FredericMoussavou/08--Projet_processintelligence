import { useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/api'
import useAuthStore from '../store/authStore'

export default function ProfilePage() {
  const { user, organizations, currentOrg, setCurrentOrg, logout } = useAuthStore()

  const [passwordForm, setPasswordForm] = useState({
    current_password : '',
    new_password     : '',
    confirm_password : '',
  })
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState('')
  const [success,  setSuccess]  = useState('')

  const handlePasswordChange = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')

    if (passwordForm.new_password !== passwordForm.confirm_password) {
      setError('Les mots de passe ne correspondent pas')
      return
    }
    if (passwordForm.new_password.length < 8) {
      setError('Le nouveau mot de passe doit faire au moins 8 caractères')
      return
    }

    setLoading(true)
    try {
      await api.post('/auth/change-password/', {
        current_password: passwordForm.current_password,
        new_password    : passwordForm.new_password,
      })
      setSuccess('Mot de passe modifié avec succès')
      setPasswordForm({ current_password: '', new_password: '', confirm_password: '' })
    } catch (err) {
      setError(err.response?.data?.error || 'Erreur lors du changement de mot de passe')
    } finally {
      setLoading(false)
    }
  }

  const ROLE_LABELS = {
    admin   : 'Administrateur',
    director: 'Directeur',
    manager : 'Manager',
    viewer  : 'Lecteur',
  }

  const ROLE_COLORS = {
    admin   : 'bg-purple-100 text-purple-700',
    director: 'bg-blue-100 text-blue-700',
    manager : 'bg-green-100 text-green-700',
    viewer  : 'bg-gray-100 text-gray-600',
  }

  return (
    <div className="p-8 max-w-2xl mx-auto space-y-6">

      {/* Header */}
      <div>
        <Link to="/" className="text-xs text-gray-400 hover:text-secondary inline-block mb-2">
          ← Tableau de bord
        </Link>
        <h2 className="text-2xl font-bold text-primary">Mon profil</h2>
      </div>

      {/* Infos utilisateur */}
      <div className="bg-white rounded-xl border border-light p-6">
        <h3 className="font-semibold text-primary mb-4">Informations du compte</h3>
        <div className="flex items-center gap-4 mb-6">
          <div className="w-14 h-14 rounded-full bg-secondary/10 flex items-center justify-center">
            <span className="text-xl font-bold text-secondary">
              {user?.username?.[0]?.toUpperCase()}
            </span>
          </div>
          <div>
            <p className="font-semibold text-primary text-lg">{user?.username}</p>
            <p className="text-sm text-gray-400">{user?.email}</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-xs text-gray-400 mb-1">Nom d'utilisateur</p>
            <p className="font-medium text-primary">{user?.username}</p>
          </div>
          <div>
            <p className="text-xs text-gray-400 mb-1">Email</p>
            <p className="font-medium text-primary">{user?.email}</p>
          </div>
        </div>
      </div>

      {/* Organisations */}
      <div className="bg-white rounded-xl border border-light p-6">
        <h3 className="font-semibold text-primary mb-4">
          Mes organisations ({organizations.length})
        </h3>
        <div className="space-y-3">
          {organizations.map((org) => (
            <div
              key={org.id}
              className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${
                currentOrg?.id === org.id
                  ? 'bg-blue-50 border border-secondary/30'
                  : 'bg-background hover:bg-light'
              }`}
              onClick={() => setCurrentOrg(org)}
            >
              <div>
                <p className="text-sm font-medium text-primary">{org.name}</p>
                <p className="text-xs text-gray-400 mt-0.5">{org.sector}</p>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${ROLE_COLORS[org.role] || ROLE_COLORS.viewer}`}>
                  {ROLE_LABELS[org.role] || org.role}
                </span>
                {currentOrg?.id === org.id && (
                  <span className="text-xs text-secondary font-medium">Active</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Changement de mot de passe */}
      <div className="bg-white rounded-xl border border-light p-6">
        <h3 className="font-semibold text-primary mb-4">Changer le mot de passe</h3>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-4 text-sm">
            {error}
          </div>
        )}
        {success && (
          <div className="bg-green-50 border border-green-200 text-green-700 rounded-lg p-3 mb-4 text-sm">
            {success}
          </div>
        )}

        <form onSubmit={handlePasswordChange} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-primary mb-1">
              Mot de passe actuel
            </label>
            <input
              type="password"
              value={passwordForm.current_password}
              onChange={(e) => setPasswordForm({ ...passwordForm, current_password: e.target.value })}
              className="w-full border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-primary mb-1">
              Nouveau mot de passe
            </label>
            <input
              type="password"
              value={passwordForm.new_password}
              onChange={(e) => setPasswordForm({ ...passwordForm, new_password: e.target.value })}
              className="w-full border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary"
              placeholder="8 caractères minimum"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-primary mb-1">
              Confirmer le nouveau mot de passe
            </label>
            <input
              type="password"
              value={passwordForm.confirm_password}
              onChange={(e) => setPasswordForm({ ...passwordForm, confirm_password: e.target.value })}
              className="w-full border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary"
              required
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="px-6 py-2 bg-secondary text-white rounded-lg text-sm font-medium hover:bg-primary transition-colors disabled:opacity-50"
          >
            {loading ? 'Modification...' : 'Modifier le mot de passe'}
          </button>
        </form>
      </div>

      {/* Déconnexion */}
      <div className="bg-white rounded-xl border border-light p-6">
        <h3 className="font-semibold text-primary mb-2">Session</h3>
        <p className="text-sm text-gray-400 mb-4">
          Vous serez redirigé vers la page de connexion.
        </p>
        <button
          onClick={() => { logout(); window.location.href = '/login' }}
          className="px-6 py-2 bg-white border border-red-200 text-red-600 rounded-lg text-sm font-medium hover:bg-red-50 transition-colors"
        >
          Se déconnecter
        </button>
      </div>

    </div>
  )
}