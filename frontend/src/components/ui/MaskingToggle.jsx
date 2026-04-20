import { useState } from 'react'
import { Shield, ShieldOff, AlertTriangle, X } from 'lucide-react'

/**
 * Texte exact du consentement requis pour désactiver le masquage.
 * Les mots-clés 'Anthropic' et 'États-Unis' sont vérifiés côté backend
 * (voir procedures/services/consent.py → REQUIRED_CONSENT_KEYWORDS).
 */
const CONSENT_TEXT = (
  "En désactivant le masquage des données personnelles, je consens " +
  "au transfert de mon texte à Anthropic (États-Unis) pour analyse. " +
  "Je certifie que ce texte ne contient pas de données personnelles " +
  "réelles ou que j'ai le droit de les partager."
)


/**
 * Toggle RGPD pour activer/désactiver le masquage des données personnelles
 * avant envoi au LLM externe (Anthropic).
 *
 * Comportement :
 *   - Par défaut : ON (masquage actif, toggle bleu)
 *   - Clic sur le toggle pour désactiver : ouvre une modale de consentement
 *   - La modale affiche le texte exact, l'utilisateur peut accepter ou annuler
 *   - Seul un consentement explicite désactive le masquage
 *   - Clic sur le toggle pour réactiver : immédiat, sans modale
 *
 * Props :
 *   enabled   : bool, état actuel (contrôlé par le parent)
 *   onChange  : function(newEnabled, consentText?) — appelée après confirmation
 *               Le consentText n'est passé que si le masquage est DÉSACTIVÉ.
 *   disabled  : bool, empêche toute interaction (défaut false)
 *
 * Usage :
 *   const [masking, setMasking] = useState(true)
 *   const [consent, setConsent] = useState('')
 *   <MaskingToggle
 *     enabled={masking}
 *     onChange={(newValue, consentText) => {
 *       setMasking(newValue)
 *       setConsent(consentText || '')
 *     }}
 *   />
 */
export default function MaskingToggle({ enabled = true, onChange, disabled = false }) {
  const [showConsentModal, setShowConsentModal] = useState(false)

  // Clic sur le toggle
  const handleToggleClick = () => {
    if (disabled) return

    if (enabled) {
      // On veut DÉSACTIVER → on demande confirmation
      setShowConsentModal(true)
    } else {
      // On veut RÉACTIVER → immédiat, pas besoin de consentement
      onChange?.(true)
    }
  }

  // Confirmation du consentement dans la modale
  const handleAcceptConsent = () => {
    setShowConsentModal(false)
    onChange?.(false, CONSENT_TEXT)
  }

  // Annulation : on ferme la modale, toggle reste ON
  const handleCancelConsent = () => {
    setShowConsentModal(false)
  }

  return (
    <>
      {/* Toggle principal */}
      <div className="flex items-start gap-3">
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          onClick={handleToggleClick}
          disabled={disabled}
          className={`
            relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full
            transition-colors duration-200 ease-in-out
            focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500
            ${enabled ? 'bg-blue-600' : 'bg-gray-300'}
            ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
          `}
        >
          <span
            className={`
              inline-block h-5 w-5 transform rounded-full bg-white shadow-md
              transition-transform duration-200 ease-in-out
              ${enabled ? 'translate-x-5' : 'translate-x-0.5'}
            `}
          />
        </button>

        <div className="flex-1">
          <div className="flex items-center gap-2">
            {enabled ? (
              <Shield size={16} className="text-blue-600" strokeWidth={2.5} />
            ) : (
              <ShieldOff size={16} className="text-gray-400" strokeWidth={2.5} />
            )}
            <span className="text-sm font-medium text-gray-900">
              Masquage des données personnelles
            </span>
          </div>
          <p className="text-xs text-gray-600 mt-0.5">
            {enabled
              ? "Les noms, emails, téléphones et identifiants sont remplacés par des tags avant l'analyse."
              : "Votre texte est envoyé tel quel à l'IA Claude (Anthropic, États-Unis)."}
          </p>
        </div>
      </div>

      {/* Modale de consentement */}
      {showConsentModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          aria-modal="true"
          role="dialog"
        >
          {/* Overlay */}
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={handleCancelConsent}
          />

          {/* Modale */}
          <div className="relative bg-white rounded-xl shadow-2xl max-w-lg w-full p-6">
            {/* Bouton fermer */}
            <button
              type="button"
              onClick={handleCancelConsent}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors"
              aria-label="Fermer"
            >
              <X size={20} />
            </button>

            {/* En-tête avec icône d'avertissement */}
            <div className="flex items-start gap-3 mb-4">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center">
                <AlertTriangle size={20} className="text-amber-600" strokeWidth={2.5} />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900">
                  Désactiver le masquage RGPD
                </h3>
                <p className="text-sm text-gray-600 mt-0.5">
                  Lisez attentivement avant de confirmer.
                </p>
              </div>
            </div>

            {/* Texte du consentement */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-4">
              <p className="text-sm text-gray-800 leading-relaxed">
                {CONSENT_TEXT}
              </p>
            </div>

            {/* Info complémentaire */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-5">
              <p className="text-xs text-blue-900">
                <strong>Traçabilité :</strong> votre consentement sera enregistré
                (date, heure, endpoint) conformément au RGPD. Vous pourrez réactiver
                le masquage à tout moment.
              </p>
            </div>

            {/* Boutons d'action */}
            <div className="flex gap-3 justify-end">
              <button
                type="button"
                onClick={handleCancelConsent}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={handleAcceptConsent}
                className="px-4 py-2 text-sm font-medium text-white bg-amber-600 rounded-lg hover:bg-amber-700 transition-colors"
              >
                Je consens et désactive le masquage
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
