import { Lock } from 'lucide-react'
import usePlanInfo from '../../hooks/usePlanInfo'
import useAuthStore from '../../store/authStore'

/**
 * Wrapper qui conditionne l'affichage ou l'activation d'un élément UI
 * selon la feature disponible dans le plan de l'organisation courante.
 *
 * Props :
 *   feature   : nom de la feature à vérifier (ex: 'export_bpmn', 'custom_theme')
 *               Doit correspondre à une clé de plan.features côté backend.
 *   children  : le composant à protéger (bouton, lien, etc.)
 *   mode      : 'disable' (défaut) | 'hide'
 *               'disable' : affiche le composant grisé avec tooltip + badge Pro
 *               'hide'    : cache complètement le composant si pas autorisé
 *   requiredPlan : libellé du plan requis à afficher dans le tooltip
 *                  (défaut 'Pro' — peut être 'Business' pour des features très haut de gamme)
 *
 * Usage :
 *   <FeatureLock feature="export_bpmn">
 *     <button onClick={exportBPMN}>BPMN</button>
 *   </FeatureLock>
 *
 * Note : la vérification côté backend reste obligatoire. Ce composant ne sert
 * qu'à améliorer l'UX — il ne remplace pas un vrai contrôle d'autorisation.
 */
export default function FeatureLock({
  feature,
  children,
  mode = 'disable',
  requiredPlan = 'Pro',
}) {
  const { currentOrg } = useAuthStore()
  const { data: planData, isLoading } = usePlanInfo(currentOrg?.id)

  // Pendant le chargement, on rend les enfants tels quels (évite de flasher
  // un état grisé avant que le plan soit connu).
  if (isLoading || !planData) {
    return <>{children}</>
  }

  const isAllowed = planData.plan?.features?.[feature] === true

  // Feature autorisée : on rend l'enfant normalement
  if (isAllowed) {
    return <>{children}</>
  }

  // Feature non autorisée
  if (mode === 'hide') {
    return null
  }

  // Mode 'disable' : on rend un wrapper qui grise l'enfant et affiche un tooltip
  return (
    <span
      className="relative inline-flex"
      title={`Disponible dans le plan ${requiredPlan}`}
    >
      {/* L'enfant est grisé et non cliquable */}
      <span
        className="opacity-40 pointer-events-none select-none"
        aria-disabled="true"
      >
        {children}
      </span>

      {/* Petit badge cadenas + "Pro" superposé */}
      <span
        className="absolute -top-1.5 -right-1.5 inline-flex items-center gap-0.5 bg-gray-800 text-white text-[10px] font-semibold px-1.5 py-0.5 rounded-full shadow-sm pointer-events-none"
      >
        <Lock size={10} strokeWidth={3} />
        {requiredPlan}
      </span>
    </span>
  )
}
