import { Crown, Sparkles, Building2 } from 'lucide-react'

/**
 * Badge coloré indiquant le plan actuel de l'organisation.
 *
 * Props :
 *   planId  : 'free' | 'pro' | 'business'
 *   size    : 'sm' | 'md' (défaut 'md')
 *
 * Usage :
 *   <PlanBadge planId="pro" />
 *   <PlanBadge planId="business" size="sm" />
 */
export default function PlanBadge({ planId = 'free', size = 'md' }) {
  const config = {
    free: {
      label: 'Free',
      Icon: null,
      classes: 'bg-gray-100 text-gray-700 border-gray-200',
      title: 'Plan gratuit — limites de base',
    },
    pro: {
      label: 'Pro',
      Icon: Sparkles,
      classes: 'bg-blue-50 text-blue-700 border-blue-200',
      title: 'Plan Pro — analyse IA Claude Haiku',
    },
    business: {
      label: 'Business',
      Icon: Crown,
      classes: 'bg-purple-50 text-purple-700 border-purple-200',
      title: 'Plan Business — analyse IA Claude Sonnet + features avancées',
    },
  }

  // Fallback sur Free si le planId est inconnu (défensif)
  const plan = config[planId] || config.free
  const { Icon } = plan

  const sizeClasses =
    size === 'sm'
      ? 'text-xs px-2 py-0.5 gap-1'
      : 'text-sm px-3 py-1 gap-1.5'

  const iconSize = size === 'sm' ? 12 : 14

  return (
    <span
      title={plan.title}
      className={`inline-flex items-center rounded-full border font-medium ${plan.classes} ${sizeClasses}`}
    >
      {Icon && <Icon size={iconSize} strokeWidth={2.5} />}
      {plan.label}
    </span>
  )
}
