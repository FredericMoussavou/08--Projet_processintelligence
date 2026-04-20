import { AlertTriangle, Infinity as InfinityIcon } from 'lucide-react'

/**
 * Barre de progression du quota mensuel d'analyses.
 *
 * Props :
 *   count          : nombre actuel d'analyses ce mois
 *   limit          : limite mensuelle (null = illimité)
 *   percentageUsed : pourcentage utilisé (0-100)
 *   quotaReached   : bool, true si count >= limit
 *   compact        : bool, version compacte sans label détaillé (défaut false)
 *
 * Usage :
 *   <QuotaBar count={42} limit={500} percentageUsed={8.4} quotaReached={false} />
 *   <QuotaBar count={50} limit={null} compact />
 */
export default function QuotaBar({
  count = 0,
  limit = null,
  percentageUsed = 0,
  quotaReached = false,
  compact = false,
}) {
  // Cas spécial : illimité (plan Business)
  if (limit === null) {
    return (
      <div className={compact ? '' : 'space-y-1'}>
        {!compact && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-700">Analyses ce mois-ci</span>
            <span className="inline-flex items-center gap-1 text-purple-700 font-medium">
              <InfinityIcon size={14} strokeWidth={2.5} />
              Illimitées
            </span>
          </div>
        )}
        <div className="h-2 rounded-full bg-gradient-to-r from-purple-200 via-purple-400 to-purple-200" />
        {!compact && (
          <p className="text-xs text-gray-500">{count} analyses effectuées ce mois</p>
        )}
      </div>
    )
  }

  // Clamp défensif du pourcentage dans [0, 100]
  const pct = Math.max(0, Math.min(100, percentageUsed))

  // Code couleur selon l'usage
  let barColor = 'bg-emerald-500'
  let textColor = 'text-emerald-700'
  if (pct >= 90) {
    barColor = 'bg-red-500'
    textColor = 'text-red-700'
  } else if (pct >= 70) {
    barColor = 'bg-amber-500'
    textColor = 'text-amber-700'
  }

  return (
    <div className={compact ? '' : 'space-y-1.5'}>
      {!compact && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-700">Analyses ce mois-ci</span>
          <span className={`font-medium ${textColor}`}>
            {count.toLocaleString('fr-FR')} / {limit.toLocaleString('fr-FR')}
          </span>
        </div>
      )}

      {/* Barre de progression */}
      <div className="h-2 rounded-full bg-gray-200 overflow-hidden">
        <div
          className={`h-full ${barColor} transition-all duration-500 ease-out`}
          style={{ width: `${pct}%` }}
          role="progressbar"
          aria-valuenow={count}
          aria-valuemin={0}
          aria-valuemax={limit}
          aria-label={`${count} analyses sur ${limit} autorisées ce mois`}
        />
      </div>

      {/* Message quota atteint */}
      {quotaReached && !compact && (
        <div className="flex items-start gap-2 mt-2 p-2 rounded-md bg-red-50 border border-red-200">
          <AlertTriangle size={16} className="text-red-600 flex-shrink-0 mt-0.5" strokeWidth={2.5} />
          <div className="text-xs text-red-800">
            <strong>Quota mensuel atteint.</strong>{' '}
            Les nouvelles analyses utilisent le mode standard. Passez à un plan supérieur
            pour retrouver l'analyse IA Premium.
          </div>
        </div>
      )}

      {/* Label compact */}
      {compact && (
        <p className={`text-xs ${textColor}`}>
          {count} / {limit}
        </p>
      )}
    </div>
  )
}
