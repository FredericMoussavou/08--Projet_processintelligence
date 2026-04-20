import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { proceduresAPI, changeRequestsAPI } from '../../services/api'
import useAuthStore from '../../store/authStore'
import usePlanInfo from '../../hooks/usePlanInfo'
import useOrgUsage from '../../hooks/useOrgUsage'
import PlanBadge from '../../components/ui/PlanBadge'
import QuotaBar from '../../components/ui/QuotaBar'

function ScoreRing({ score, label, color }) {
  const pct    = Math.round(score * 100)
  const radius = 28
  const circ   = 2 * Math.PI * radius
  const dash   = (pct / 100) * circ

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-20 h-20">
        <svg className="w-20 h-20 -rotate-90" viewBox="0 0 72 72">
          <circle cx="36" cy="36" r={radius} fill="none" stroke="#E5E7EB" strokeWidth="6"/>
          <circle
            cx="36" cy="36" r={radius} fill="none"
            stroke={color} strokeWidth="6"
            strokeDasharray={`${dash} ${circ}`}
            strokeLinecap="round"
            style={{ transition: 'stroke-dasharray 1s ease' }}
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-lg font-bold text-primary">
          {pct}%
        </span>
      </div>
      <span className="text-xs text-gray-500 text-center leading-tight">{label}</span>
    </div>
  )
}

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

function CRStatusBadge({ status }) {
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

export default function DashboardHome() {
  const { currentOrg, user } = useAuthStore()

  const [procedures,    setProcedures]    = useState([])
  const [changeReqs,    setChangeReqs]    = useState([])
  const [loading,       setLoading]       = useState(true)

  // Plan et usage de l'organisation (via React Query, mis en cache)
  const { data: planData }  = usePlanInfo(currentOrg?.id)
  const { data: usageData } = useOrgUsage(currentOrg?.id)

  useEffect(() => {
    if (!currentOrg) return

    const load = async () => {
      setLoading(true)
      try {
        const [procRes, crRes] = await Promise.all([
          proceduresAPI.list(currentOrg.id),
          changeRequestsAPI.list({ status: 'awaiting_review' }),
        ])
        setProcedures(procRes.data.procedures || [])
        setChangeReqs(crRes.data.results || [])
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [currentOrg])

  // Calcul des stats
  const total    = procedures.length
  const active   = procedures.filter(p => p.status === 'active').length
  const archived = procedures.filter(p => p.status === 'archived').length
  const drafts   = procedures.filter(p => p.status === 'draft').length
  const pending  = changeReqs.length
  const recent   = [...procedures].slice(0, 5)

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center h-64">
        <div className="text-gray-400 text-sm">Chargement...</div>
      </div>
    )
  }

  return (
    <div className="p-8 space-y-8">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-primary">
            Bonjour, {user?.username} 👋
          </h2>
          <p className="text-gray-500 text-sm mt-1">
            {currentOrg?.name} — {new Date().toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })}
          </p>
        </div>
        <Link
          to="/procedures/ingest"
          className="bg-secondary text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary transition-colors"
        >
          + Nouvelle procédure
        </Link>
      </div>

      {/* Bloc "Mon plan" */}
      {planData && usageData && (
        <div className="bg-white rounded-xl border border-light p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <h3 className="font-semibold text-primary">Mon plan</h3>
              <PlanBadge planId={planData.plan.id} />
            </div>
            <p className="text-xs text-gray-400">
              {planData.plan.description}
            </p>
          </div>

          <div className="grid grid-cols-3 gap-6">
            {/* Analyses mensuelles */}
            <div className="col-span-2">
              <QuotaBar
                count={usageData.analyses.count}
                limit={usageData.analyses.limit}
                percentageUsed={usageData.analyses.percentage_used}
                quotaReached={usageData.analyses.quota_reached}
              />
            </div>

            {/* Procédures et utilisateurs */}
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Procédures</span>
                <span className="font-medium text-primary">
                  {usageData.procedures.count}
                  {usageData.procedures.limit !== null && ` / ${usageData.procedures.limit}`}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Utilisateurs</span>
                <span className="font-medium text-primary">
                  {usageData.users.count}
                  {usageData.users.limit !== null && ` / ${usageData.users.limit}`}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Stats cards */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Total procédures', value: total,    color: 'text-primary',  bg: 'bg-blue-50' },
          { label: 'Actives',          value: active,   color: 'text-green-700', bg: 'bg-green-50' },
          { label: 'Brouillons',       value: drafts,   color: 'text-yellow-700',bg: 'bg-yellow-50' },
          { label: 'En attente',       value: pending,  color: 'text-orange-700',bg: 'bg-orange-50' },
        ].map((stat) => (
          <div key={stat.label} className={`${stat.bg} rounded-xl p-4 border border-white`}>
            <p className="text-xs text-gray-500 mb-1">{stat.label}</p>
            <p className={`text-3xl font-bold ${stat.color}`}>{stat.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-6">

        {/* Procédures récentes */}
        <div className="col-span-2 bg-white rounded-xl border border-light p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-primary">Procédures récentes</h3>
            <Link to="/procedures" className="text-xs text-secondary hover:underline">
              Voir tout →
            </Link>
          </div>

          {recent.length === 0 ? (
            <div className="text-center py-8 text-gray-400 text-sm">
              Aucune procédure —
              <Link to="/procedures/ingest" className="text-secondary hover:underline ml-1">
                créez-en une
              </Link>
            </div>
          ) : (
            <div className="space-y-3">
              {recent.map((proc) => (
                <Link
                  key={proc.id}
                  to={`/procedures/${proc.id}`}
                  className="flex items-center justify-between p-3 rounded-lg hover:bg-background transition-colors group"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-primary group-hover:text-secondary truncate">
                      {proc.title}
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {proc.service || 'Sans service'} · v{proc.version}
                    </p>
                  </div>
                  <div className="ml-3 flex-shrink-0">
                    <StatusBadge status={proc.status} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Demandes en attente */}
        <div className="bg-white rounded-xl border border-light p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-primary">Demandes en attente</h3>
            <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full font-medium">
              {pending}
            </span>
          </div>

          {changeReqs.length === 0 ? (
            <div className="text-center py-8 text-gray-400 text-sm">
              Aucune demande en attente
            </div>
          ) : (
            <div className="space-y-3">
              {changeReqs.slice(0, 5).map((cr) => (
                <div key={cr.id} className="p-3 rounded-lg bg-background">
                  <p className="text-sm font-medium text-primary truncate">
                    {cr.procedure_title}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    v{cr.procedure_version} · {cr.created_at}
                  </p>
                  <div className="mt-2">
                    <CRStatusBadge status={cr.status} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>

      {/* Répartition par service */}
      {procedures.length > 0 && (
        <div className="bg-white rounded-xl border border-light p-6">
          <h3 className="font-semibold text-primary mb-4">Répartition par service</h3>
          <div className="flex flex-wrap gap-3">
            {Object.entries(
              procedures.reduce((acc, p) => {
                const svc = p.service || 'Sans service'
                acc[svc] = (acc[svc] || 0) + 1
                return acc
              }, {})
            ).map(([svc, count]) => (
              <Link
                key={svc}
                to={`/procedures?service=${svc}`}
                className="flex items-center gap-2 bg-background hover:bg-light px-4 py-2 rounded-lg transition-colors"
              >
                <span className="text-sm font-medium text-primary">{svc}</span>
                <span className="text-xs bg-secondary text-white px-1.5 py-0.5 rounded-full">
                  {count}
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}

    </div>
  )
}
