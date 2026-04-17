import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { proceduresAPI } from '../../services/api'
import useAuthStore from '../../store/authStore'

function StatusBadge({ status }) {
  const styles = {
    active  : 'bg-green-100 text-green-700',
    draft   : 'bg-yellow-100 text-yellow-700',
    archived: 'bg-gray-100 text-gray-500',
  }
  const labels = {
    active  : 'Active',
    draft   : 'Brouillon',
    archived: 'Archivée',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${styles[status] || styles.draft}`}>
      {labels[status] || status}
    </span>
  )
}

const STATUS_FILTERS = [
  { value: '',         label: 'Toutes' },
  { value: 'active',   label: 'Actives' },
  { value: 'draft',    label: 'Brouillons' },
  { value: 'archived', label: 'Archivées' },
]

export default function ProceduresList() {
  const { currentOrg } = useAuthStore()
  const [searchParams, setSearchParams] = useSearchParams()

  const [procedures, setProcedures] = useState([])
  const [services,   setServices]   = useState([])
  const [loading,    setLoading]    = useState(true)
  const [search,     setSearch]     = useState('')

  const statusFilter  = searchParams.get('status')  || ''
  const serviceFilter = searchParams.get('service') || ''

  useEffect(() => {
    if (!currentOrg) return

    const load = async () => {
      setLoading(true)
      try {
        const params = {}
        if (statusFilter)  params.status  = statusFilter
        if (serviceFilter) params.service = serviceFilter

        const res = await proceduresAPI.list(currentOrg.id, params)
        const procs = res.data.procedures || []
        setProcedures(procs)

        // Extrait les services uniques
        const svcs = [...new Set(procs.map(p => p.service).filter(Boolean))]
        setServices(svcs)
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [currentOrg, statusFilter, serviceFilter])

  const setFilter = (key, value) => {
    const params = Object.fromEntries(searchParams)
    if (value) params[key] = value
    else delete params[key]
    setSearchParams(params)
  }

  // Filtre local par recherche texte
  const filtered = procedures.filter(p =>
    p.title.toLowerCase().includes(search.toLowerCase()) ||
    (p.service || '').toLowerCase().includes(search.toLowerCase())
  )

  const handleExportPdf = async (id, e) => {
    e.preventDefault()
    try {
      const res = await proceduresAPI.exportPdf(id)
      const url = URL.createObjectURL(new Blob([res.data]))
      const a   = document.createElement('a')
      a.href    = url
      a.download = `audit_${id}.pdf`
      a.click()
    } catch (err) {
      console.error(err)
    }
  }

  return (
    <div className="p-8 space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-primary">Procédures</h2>
          <p className="text-gray-500 text-sm mt-1">
            {filtered.length} procédure{filtered.length > 1 ? 's' : ''}
            {statusFilter && ` · ${STATUS_FILTERS.find(f => f.value === statusFilter)?.label}`}
            {serviceFilter && ` · ${serviceFilter}`}
          </p>
        </div>
        <Link
          to="/procedures/ingest"
          className="bg-secondary text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary transition-colors"
        >
          + Nouvelle procédure
        </Link>
      </div>

      {/* Filtres */}
      <div className="flex flex-wrap gap-3 items-center">

        {/* Recherche */}
        <input
          type="text"
          placeholder="Rechercher..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="border border-light rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-secondary w-56"
        />

        {/* Filtre statut */}
        <div className="flex gap-1 bg-background rounded-lg p-1">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter('status', f.value)}
              className={`px-3 py-1 rounded-md text-sm transition-colors ${
                statusFilter === f.value
                  ? 'bg-white text-primary font-medium shadow-sm'
                  : 'text-gray-500 hover:text-primary'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Filtre service */}
        {services.length > 0 && (
          <select
            value={serviceFilter}
            onChange={(e) => setFilter('service', e.target.value)}
            className="border border-light rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-secondary bg-white"
          >
            <option value="">Tous les services</option>
            {services.map(svc => (
              <option key={svc} value={svc}>{svc}</option>
            ))}
          </select>
        )}
      </div>

      {/* Liste */}
      {loading ? (
        <div className="text-center py-16 text-gray-400 text-sm">Chargement...</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-gray-400 text-sm">Aucune procédure trouvée</p>
          <Link to="/procedures/ingest" className="text-secondary text-sm hover:underline mt-2 inline-block">
            Créer une procédure →
          </Link>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-light overflow-hidden">
          <table className="w-full">
            <thead className="bg-background border-b border-light">
              <tr>
                <th className="text-left text-xs font-medium text-gray-500 px-6 py-3">Titre</th>
                <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Service</th>
                <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Version</th>
                <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Statut</th>
                <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Mise à jour</th>
                <th className="text-right text-xs font-medium text-gray-500 px-6 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-light">
              {filtered.map((proc) => (
                <tr key={proc.id} className="hover:bg-background transition-colors group">
                  <td className="px-6 py-4">
                    <Link
                      to={`/procedures/${proc.id}`}
                      className="text-sm font-medium text-primary group-hover:text-secondary"
                    >
                      {proc.title}
                    </Link>
                    {proc.archived_at && (
                      <p className="text-xs text-gray-400 mt-0.5">
                        Archivée le {proc.archived_at}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-4">
                    <span className="text-sm text-gray-600">
                      {proc.service || <span className="text-gray-300">—</span>}
                    </span>
                  </td>
                  <td className="px-4 py-4">
                    <span className="text-sm font-mono text-gray-600">v{proc.version}</span>
                  </td>
                  <td className="px-4 py-4">
                    <StatusBadge status={proc.status} />
                  </td>
                  <td className="px-4 py-4">
                    <span className="text-xs text-gray-400">{proc.updated_at}</span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center justify-end gap-2">
                      <Link
                        to={`/procedures/${proc.id}`}
                        className="text-xs text-secondary hover:underline"
                      >
                        Détail
                      </Link>
                      <button
                        onClick={(e) => handleExportPdf(proc.id, e)}
                        className="text-xs text-gray-400 hover:text-primary"
                      >
                        PDF
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}