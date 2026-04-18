import { useState } from 'react'
import { Link } from 'react-router-dom'
import { manualAPI } from '../services/api'
import useAuthStore from '../store/authStore'

export default function ManualPage() {
  const { currentOrg } = useAuthStore()

  const [filters,  setFilters]  = useState({ service: '', role: '' })
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState('')
  const [success,  setSuccess]  = useState(false)

  const handleGenerate = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess(false)
    setLoading(true)

    try {
      const params = {}
      if (filters.service) params.service = filters.service
      if (filters.role)    params.role    = filters.role

      const res = await manualAPI.generate(currentOrg?.id || 1, params)

      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
      const a   = document.createElement('a')
      a.href    = url
      a.download = `manuel_procedures_${currentOrg?.name || 'organisation'}.pdf`
      a.click()
      URL.revokeObjectURL(url)
      setSuccess(true)
    } catch (err) {
      setError(err.response?.data?.error || 'Erreur lors de la génération')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-8 max-w-xl mx-auto space-y-6">

      {/* Header */}
      <div>
        <Link to="/procedures" className="text-xs text-gray-400 hover:text-secondary inline-block mb-2">
          ← Procédures
        </Link>
        <h2 className="text-2xl font-bold text-primary">Manuel de procédures</h2>
        <p className="text-gray-500 text-sm mt-1">
          Génère un PDF compilant toutes les procédures actives de l'organisation
        </p>
      </div>

      {/* Formulaire */}
      <div className="bg-white rounded-xl border border-light p-6">
        <h3 className="font-semibold text-primary mb-4">Options de filtrage</h3>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-4 text-sm">
            {error}
          </div>
        )}

        {success && (
          <div className="bg-green-50 border border-green-200 text-green-700 rounded-lg p-3 mb-4 text-sm">
            ✅ Manuel généré et téléchargé avec succès
          </div>
        )}

        <form onSubmit={handleGenerate} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-primary mb-1">
              Filtrer par service
            </label>
            <input
              type="text"
              value={filters.service}
              onChange={(e) => setFilters({ ...filters, service: e.target.value })}
              className="w-full border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary"
              placeholder="Ex: RH, Comptabilité... (laisser vide = tous)"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-primary mb-1">
              Filtrer par rôle / poste
            </label>
            <input
              type="text"
              value={filters.role}
              onChange={(e) => setFilters({ ...filters, role: e.target.value })}
              className="w-full border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary"
              placeholder="Ex: Comptable, Manager... (laisser vide = tous)"
            />
          </div>

          <div className="bg-background rounded-lg p-4 text-xs text-gray-500 space-y-1">
            <p>📄 Le manuel inclut toutes les procédures <strong>actives</strong> de l'organisation</p>
            <p>🔍 Les filtres permettent de générer un manuel ciblé par service ou par rôle</p>
            <p>📊 Chaque procédure inclut ses étapes, acteurs et scores d'automatisation</p>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-secondary text-white py-3 rounded-xl text-sm font-semibold hover:bg-primary transition-colors disabled:opacity-50"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
                Génération en cours...
              </span>
            ) : '📄 Générer le manuel PDF'}
          </button>
        </form>
      </div>

      {/* Info */}
      <div className="bg-white rounded-xl border border-light p-6">
        <h3 className="font-semibold text-primary mb-3">Contenu du manuel</h3>
        <div className="space-y-2 text-sm text-gray-500">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-secondary flex-shrink-0"/>
            Page de couverture avec le nom de l'organisation
          </div>
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-secondary flex-shrink-0"/>
            Table des matières automatique
          </div>
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-secondary flex-shrink-0"/>
            Détail de chaque procédure avec ses étapes
          </div>
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-secondary flex-shrink-0"/>
            Scores d'optimisation et d'automatisation
          </div>
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-secondary flex-shrink-0"/>
            Mise en page thématisée aux couleurs de l'organisation
          </div>
        </div>
      </div>

    </div>
  )
}