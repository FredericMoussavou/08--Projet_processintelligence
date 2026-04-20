import useAuthStore from '../../store/authStore'
import { Outlet, NavLink, Link, useNavigate } from 'react-router-dom'
import usePlanInfo from '../../hooks/usePlanInfo'
import useOrgUsage from '../../hooks/useOrgUsage'
import PlanBadge from '../ui/PlanBadge'
import QuotaBar from '../ui/QuotaBar'

export default function DashboardLayout() {
  const { user, currentOrg, organizations, setCurrentOrg, logout } = useAuthStore()
  const navigate = useNavigate()

  // Récupère plan et usage de l'organisation courante
  const { data: planData }  = usePlanInfo(currentOrg?.id)
  const { data: usageData } = useOrgUsage(currentOrg?.id)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navItems = [
    { to: '/',            label: 'Tableau de bord', end: true },
    { to: '/procedures',  label: 'Procédures' },
    { to: '/change-requests', label: 'Demandes' },
    { to: '/admin',           label: 'Administration' },
    { to: '/manual', label: 'Manuel PDF' },
  ]

  return (
    <div className="min-h-screen flex">

      {/* Sidebar */}
      <aside className="w-64 bg-primary text-white flex flex-col">

        {/* Logo */}
        <div className="p-6 border-b border-white/10">
          <h1 className="text-lg font-bold">ProcessIntelligence</h1>
          <p className="text-xs text-white/60 mt-1">Audit & Optimisation</p>
        </div>

        {/* Organisation selector */}
        {organizations.length > 1 && (
          <div className="p-4 border-b border-white/10">
            <select
              value={currentOrg?.id || ''}
              onChange={(e) => {
                const org = organizations.find(o => o.id === parseInt(e.target.value))
                setCurrentOrg(org)
              }}
              className="w-full bg-white/10 text-white text-sm rounded-lg px-3 py-2 border border-white/20"
            >
              {organizations.map((org) => (
                <option key={org.id} value={org.id} className="text-primary bg-white">
                  {org.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Organisation courante + badge plan + quota */}
        {currentOrg && (
          <div className="px-6 py-3 border-b border-white/10 space-y-2">
            {organizations.length === 1 && (
              <>
                <p className="text-xs text-white/60">Organisation</p>
                <p className="text-sm font-medium">{currentOrg.name}</p>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs bg-white/20 px-2 py-0.5 rounded-full">
                    {currentOrg.role}
                  </span>
                  {planData?.plan?.id && (
                    <PlanBadge planId={planData.plan.id} size="sm" />
                  )}
                </div>
              </>
            )}
            {organizations.length > 1 && planData?.plan?.id && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-white/60">Plan :</span>
                <PlanBadge planId={planData.plan.id} size="sm" />
              </div>
            )}

            {/* Mini QuotaBar (analyses du mois) */}
            {usageData?.analyses && (
              <div className="pt-2">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-white/60">Analyses/mois</span>
                  <span className="text-xs text-white/80 font-medium">
                    {usageData.analyses.count}
                    {usageData.analyses.limit !== null && ` / ${usageData.analyses.limit}`}
                  </span>
                </div>
                {usageData.analyses.limit !== null ? (
                  <QuotaBar
                    count={usageData.analyses.count}
                    limit={usageData.analyses.limit}
                    percentageUsed={usageData.analyses.percentage_used}
                    quotaReached={usageData.analyses.quota_reached}
                    compact
                  />
                ) : (
                  <div className="h-2 rounded-full bg-gradient-to-r from-purple-400 via-purple-300 to-purple-400" />
                )}
              </div>
            )}
          </div>
        )}

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `block px-4 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-white/20 text-white font-medium'
                    : 'text-white/70 hover:bg-white/10 hover:text-white'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* User info + logout */}
        <div className="p-4 border-t border-white/10">
          <p className="text-sm font-medium">{user?.username}</p>
          <p className="text-xs text-white/60">{user?.email}</p>
          <Link
            to="/profile"
            className="block text-xs text-white/60 hover:text-white mb-2 transition-colors"
            >
            Mon profil
          </Link>
          <button
            onClick={handleLogout}
            className="mt-3 w-full text-xs text-white/60 hover:text-white text-left transition-colors"
          >
            Se déconnecter →
          </button>
        </div>

      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>

    </div>
  )
}
