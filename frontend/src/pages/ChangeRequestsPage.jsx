import { useEffect, useState } from 'react'
import { changeRequestsAPI } from '../services/api'
import useAuthStore from '../store/authStore'
import { Link } from 'react-router-dom'

function StatusBadge({ status }) {
  const styles = {
    approved        : 'bg-green-100 text-green-700',
    auto_approved   : 'bg-green-100 text-green-700',
    auto_rejected   : 'bg-red-100 text-red-700',
    rejected        : 'bg-red-100 text-red-700',
    awaiting_review : 'bg-yellow-100 text-yellow-700',
    pending         : 'bg-blue-100 text-blue-700',
  }
  const labels = {
    approved        : 'Approuvée',
    auto_approved   : 'Auto-approuvée',
    auto_rejected   : 'Auto-rejetée',
    rejected        : 'Rejetée',
    awaiting_review : 'En attente',
    pending         : 'En cours',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${styles[status] || 'bg-gray-100 text-gray-500'}`}>
      {labels[status] || status}
    </span>
  )
}

function ChangeTypeBadge({ type }) {
  const styles = {
    patch: 'bg-gray-100 text-gray-600',
    minor: 'bg-blue-100 text-blue-600',
    major: 'bg-purple-100 text-purple-600',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${styles[type] || styles.patch}`}>
      {type}
    </span>
  )
}

const STATUS_FILTERS = [
  { value: '',                label: 'Toutes' },
  { value: 'awaiting_review', label: 'En attente' },
  { value: 'approved',        label: 'Approuvées' },
  { value: 'rejected',        label: 'Rejetées' },
  { value: 'auto_rejected',   label: 'Auto-rejetées' },
]

export default function ChangeRequestsPage() {
  const { canApprove, currentOrg } = useAuthStore()

  const [requests,     setRequests]     = useState([])
  const [loading,      setLoading]      = useState(true)
  const [statusFilter, setStatusFilter] = useState('')
  const [selected,     setSelected]     = useState(null)
  const [actionLoading,setActionLoading]= useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [showReject,   setShowReject]   = useState(false)
  const [comment,      setComment]      = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const params = {}
      if (statusFilter)      params.status          = statusFilter
      if (currentOrg?.id)    params.organization_id = currentOrg.id
      const res = await changeRequestsAPI.list(params)
      setRequests(res.data.results || [])
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [statusFilter])

  const handleApprove = async () => {
    if (!selected) return
    setActionLoading(true)
    try {
      await changeRequestsAPI.approve(selected.id, { comment })
      setSelected(null)
      setComment('')
      load()
    } catch (err) {
      console.error(err)
    } finally {
      setActionLoading(false)
    }
  }

  const handleReject = async () => {
    if (!selected || !rejectReason.trim()) return
    setActionLoading(true)
    try {
      await changeRequestsAPI.reject(selected.id, { reason: rejectReason })
      setSelected(null)
      setRejectReason('')
      setShowReject(false)
      load()
    } catch (err) {
      console.error(err)
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <div className="p-8 space-y-6">

      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-primary">Demandes de changement</h2>
        <p className="text-gray-500 text-sm mt-1">
          Workflow de validation des modifications de procédures
        </p>
      </div>

      {/* Filtres */}
      <div className="flex gap-1 bg-background rounded-lg p-1 w-fit">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setStatusFilter(f.value)}
            className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
              statusFilter === f.value
                ? 'bg-white text-primary font-medium shadow-sm'
                : 'text-gray-500 hover:text-primary'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-6">

        {/* Liste */}
        <div className="col-span-2 space-y-3">
          {loading ? (
            <div className="text-center py-16 text-gray-400 text-sm">Chargement...</div>
          ) : requests.length === 0 ? (
            <div className="text-center py-16 text-gray-400 text-sm">
              Aucune demande trouvée
            </div>
          ) : (
            requests.map((cr) => (
              <div
                key={cr.id}
                onClick={() => setSelected(cr)}
                className={`bg-white rounded-xl border p-5 cursor-pointer transition-all ${
                  selected?.id === cr.id
                    ? 'border-secondary shadow-sm'
                    : 'border-light hover:border-secondary/50'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <p className="text-sm font-medium text-primary truncate">
                        {cr.procedure_title}
                      </p>
                      <span className="text-xs font-mono text-gray-400 flex-shrink-0">
                        v{cr.procedure_version}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 line-clamp-2">{cr.location}</p>
                    <div className="flex items-center gap-2 mt-2">
                      <span className="text-xs text-gray-400">{cr.created_at}</span>
                      <span className="text-gray-200">·</span>
                      <span className="text-xs text-gray-400">
                        par {cr.requested_by}
                      </span>
                    </div>
                  </div>
                  <StatusBadge status={cr.status} />
                </div>
              </div>
            ))
          )}
        </div>

        {/* Détail + Actions */}
        <div className="space-y-4">
          {!selected ? (
            <div className="bg-white rounded-xl border border-light p-8 text-center">
              <p className="text-gray-400 text-sm">
                Sélectionnez une demande pour voir les détails
              </p>
            </div>
          ) : (
            <>
              {/* Détail */}
              <div className="bg-white rounded-xl border border-light p-5 space-y-4">
                <div className="flex items-start justify-between">
                  <h3 className="font-semibold text-primary text-sm">
                    Détail de la demande #{selected.id}
                  </h3>
                  <StatusBadge status={selected.status} />
                </div>

                <div className="space-y-3 text-sm">
                  <div>
                    <p className="text-xs text-gray-400 mb-0.5">Procédure</p>
                    <p className="font-medium text-primary">{selected.procedure_title}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400 mb-0.5">Version</p>
                    <p className="font-mono text-gray-600">v{selected.procedure_version}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400 mb-0.5">Demandé par</p>
                    <p className="text-gray-600">{selected.requested_by}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400 mb-0.5">Reviewer</p>
                    <p className="text-gray-600">{selected.reviewer}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400 mb-0.5">Localisation</p>
                    <p className="text-gray-600 text-xs leading-relaxed">{selected.location}</p>
                  </div>
                  {selected.reviewed_at && (
                    <div>
                      <p className="text-xs text-gray-400 mb-0.5">Traitée le</p>
                      <p className="text-gray-600">{selected.reviewed_at}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Actions — uniquement pour Admin/Directeur sur demandes en attente */}
              {selected.status === 'awaiting_review' && canApprove() && (
                <div className="bg-white rounded-xl border border-light p-5 space-y-3">
                  <h3 className="font-semibold text-primary text-sm">Actions</h3>

                  {!showReject ? (
                    <>
                      <div>
                        <label className="block text-xs text-gray-400 mb-1">
                          Commentaire (optionnel)
                        </label>
                        <textarea
                          value={comment}
                          onChange={(e) => setComment(e.target.value)}
                          className="w-full border border-light rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-secondary"
                          rows={2}
                          placeholder="Ajouter un commentaire..."
                        />
                      </div>
                      <button
                        onClick={handleApprove}
                        disabled={actionLoading}
                        className="w-full bg-green-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-green-700 transition-colors disabled:opacity-50"
                      >
                        {actionLoading ? 'En cours...' : '✅ Approuver'}
                      </button>
                      <button
                        onClick={() => setShowReject(true)}
                        className="w-full bg-white border border-red-200 text-red-600 py-2 rounded-lg text-sm font-medium hover:bg-red-50 transition-colors"
                      >
                        ❌ Rejeter
                      </button>
                    </>
                  ) : (
                    <>
                      <div>
                        <label className="block text-xs text-gray-400 mb-1">
                          Motif de rejet *
                        </label>
                        <textarea
                          value={rejectReason}
                          onChange={(e) => setRejectReason(e.target.value)}
                          className="w-full border border-red-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-red-400"
                          rows={3}
                          placeholder="Expliquez pourquoi cette demande est rejetée..."
                          required
                        />
                      </div>
                      <button
                        onClick={handleReject}
                        disabled={actionLoading || !rejectReason.trim()}
                        className="w-full bg-red-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-50"
                      >
                        {actionLoading ? 'En cours...' : 'Confirmer le rejet'}
                      </button>
                      <button
                        onClick={() => { setShowReject(false); setRejectReason('') }}
                        className="w-full text-xs text-gray-400 hover:text-gray-600"
                      >
                        Annuler
                      </button>
                    </>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}