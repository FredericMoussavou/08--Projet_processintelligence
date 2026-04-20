import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { proceduresAPI } from '../../services/api'
import useAuthStore from '../../store/authStore'
import MaskingToggle from '../../components/ui/MaskingToggle'
import EngineBadge from '../../components/ui/EngineBadge'

const MODES = [
  { key: 'text', label: 'Texte libre',  desc: 'Décrivez votre procédure en langage naturel' },
  { key: 'file', label: 'Fichier',      desc: 'PDF, Word, CSV ou TXT' },
]

// Doit correspondre à REQUIRED_CONSENT_KEYWORDS côté backend (procedures/services/consent.py)
const DEFAULT_CONSENT_TEXT = (
  "En désactivant le masquage des données personnelles, je consens " +
  "au transfert de mon texte à Anthropic (États-Unis) pour analyse. " +
  "Je certifie que ce texte ne contient pas de données personnelles " +
  "réelles ou que j'ai le droit de les partager."
)

export default function IngestPage() {
  const navigate    = useNavigate()
  const { currentOrg } = useAuthStore()

  const [mode,        setMode]        = useState('text')
  const [form,        setForm]        = useState({
    title         : '',
    service       : '',
    apply_masking : true,
    consent_text  : '',
  })
  const [text,        setText]        = useState('')
  const [file,        setFile]        = useState(null)
  const [loading,     setLoading]     = useState(false)
  const [error,       setError]       = useState('')
  const [result,      setResult]      = useState(null)

  const handleMaskingChange = (enabled, consentText) => {
    setForm((prev) => ({
      ...prev,
      apply_masking: enabled,
      // Si on désactive, on stocke le texte de consentement fourni par la modale
      // Si on réactive, on vide
      consent_text: enabled ? '' : (consentText || DEFAULT_CONSENT_TEXT),
    }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      let res

      if (mode === 'text') {
        res = await proceduresAPI.ingest({
          text,
          title                 : form.title,
          service               : form.service,
          organization_id       : currentOrg?.id || 1,
          apply_masking         : form.apply_masking,
          masking_consent_text  : form.consent_text,
        })
      } else {
        const formData = new FormData()
        formData.append('file',                 file)
        formData.append('title',                form.title)
        formData.append('service',              form.service)
        formData.append('organization_id',      currentOrg?.id || 1)
        formData.append('apply_masking',        form.apply_masking)
        formData.append('masking_consent_text', form.consent_text)
        res = await proceduresAPI.ingestFile(formData)
      }

      setResult(res.data)
    } catch (err) {
      setError(err.response?.data?.error || 'Erreur lors de l\'ingestion')
    } finally {
      setLoading(false)
    }
  }

  // Résultat affiché après ingestion réussie
  if (result) {
    const anomaliesCount = result.analysis?.anomalies_count || 0
    return (
      <div className="p-8 max-w-2xl mx-auto space-y-6">
        <div className="bg-green-50 border border-green-200 rounded-xl p-6">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-lg font-semibold text-green-700 mb-1">
                ✅ Procédure créée avec succès
              </h3>
              <p className="text-sm text-green-600">
                {result.steps_count} étape{result.steps_count > 1 ? 's' : ''} extraite{result.steps_count > 1 ? 's' : ''}
              </p>
            </div>
            {result.engine_used && (
              <EngineBadge engine={result.engine_used} />
            )}
          </div>

          {/* Alerte quota */}
          {result.quota?.quota_reached && (
            <div className="mt-3 text-xs text-orange-700 bg-orange-50 border border-orange-200 rounded-lg px-3 py-2">
              Quota mensuel atteint. Cette analyse a été effectuée en mode standard.
            </div>
          )}
        </div>

        {/* Scores */}
        {result.analysis && (
          <div className="bg-white rounded-xl border border-light p-6">
            <h3 className="font-semibold text-primary mb-4">Analyse automatique</h3>
            <div className="grid grid-cols-2 gap-6">
              {[
                { label: "Score d'optimisation",   value: result.analysis.score_optim },
                { label: "Score d'automatisation", value: result.analysis.score_auto  },
              ].map((s) => (
                <div key={s.label}>
                  <div className="flex justify-between mb-1">
                    <span className="text-xs text-gray-500">{s.label}</span>
                    <span className="text-sm font-bold text-primary">
                      {Math.round(s.value * 100)}%
                    </span>
                  </div>
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-secondary transition-all duration-700"
                      style={{ width: `${Math.round(s.value * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
            {anomaliesCount > 0 && (
              <p className="text-xs text-orange-600 mt-3">
                ⚠️ {anomaliesCount} anomalie{anomaliesCount > 1 ? 's' : ''} détectée{anomaliesCount > 1 ? 's' : ''}
              </p>
            )}
          </div>
        )}

        {/* Étapes extraites */}
        <div className="bg-white rounded-xl border border-light p-6">
          <h3 className="font-semibold text-primary mb-4">Étapes extraites</h3>
          <div className="space-y-2">
            {result.steps?.map((step) => (
              <div key={step.order} className="flex items-start gap-3 p-3 rounded-lg bg-background">
                <span className="text-xs font-mono font-bold text-secondary w-6 flex-shrink-0">
                  {step.order}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-primary">{step.title}</p>
                  <div className="flex gap-3 mt-1">
                    {step.actor_role && (
                      <span className="text-xs text-gray-400">{step.actor_role}</span>
                    )}
                    {step.action_verb && (
                      <span className="text-xs text-secondary">{step.action_verb}</span>
                    )}
                  </div>
                </div>
                <span className="text-xs text-gray-400 flex-shrink-0">
                  {Math.round(step.automation_score * 100)}%
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={() => navigate(`/procedures/${result.procedure_id}`)}
            className="flex-1 bg-secondary text-white py-2 rounded-lg text-sm font-medium hover:bg-primary transition-colors"
          >
            Voir la procédure →
          </button>
          <button
            onClick={() => { setResult(null); setText(''); setFile(null) }}
            className="px-4 py-2 bg-white border border-light text-primary rounded-lg text-sm hover:bg-background transition-colors"
          >
            Nouvelle procédure
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="p-8 max-w-2xl mx-auto space-y-6">

      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-primary">Nouvelle procédure</h2>
        <p className="text-gray-500 text-sm mt-1">
          Décrivez votre procédure — l'IA extrait les étapes automatiquement
        </p>
      </div>

      {/* Mode selector */}
      <div className="grid grid-cols-2 gap-3">
        {MODES.map((m) => (
          <button
            key={m.key}
            onClick={() => setMode(m.key)}
            className={`p-4 rounded-xl border-2 text-left transition-colors ${
              mode === m.key
                ? 'border-secondary bg-blue-50'
                : 'border-light bg-white hover:border-secondary/50'
            }`}
          >
            <p className="text-sm font-medium text-primary">{m.label}</p>
            <p className="text-xs text-gray-400 mt-1">{m.desc}</p>
          </button>
        ))}
      </div>

      {/* Formulaire */}
      <form onSubmit={handleSubmit} className="space-y-4">

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">
            {error}
          </div>
        )}

        {/* Titre */}
        <div>
          <label className="block text-sm font-medium text-primary mb-1">
            Titre de la procédure *
          </label>
          <input
            type="text"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            className="w-full border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary"
            placeholder="Ex: Processus de recrutement"
            required
          />
        </div>

        {/* Service */}
        <div>
          <label className="block text-sm font-medium text-primary mb-1">
            Service / Département
          </label>
          <input
            type="text"
            value={form.service}
            onChange={(e) => setForm({ ...form, service: e.target.value })}
            className="w-full border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary"
            placeholder="Ex: RH, Comptabilité, Direction..."
          />
        </div>

        {/* Contenu selon le mode */}
        {mode === 'text' ? (
          <div>
            <label className="block text-sm font-medium text-primary mb-1">
              Description de la procédure *
            </label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="w-full border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary"
              rows={8}
              placeholder="Le RH publie l'offre d'emploi sur LinkedIn. Le manager analyse les CVs dans Excel. Si un candidat est retenu, le RH organise un entretien. La DG valide l'embauche et signe le contrat."
              required
            />
            <p className="text-xs text-gray-400 mt-1">
              {text.length} / 50 000 caractères
            </p>
          </div>
        ) : (
          <div>
            <label className="block text-sm font-medium text-primary mb-1">
              Fichier *
            </label>
            <div
              className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
                file ? 'border-secondary bg-blue-50' : 'border-light hover:border-secondary/50'
              }`}
            >
              {file ? (
                <div>
                  <p className="text-sm font-medium text-secondary">{file.name}</p>
                  <p className="text-xs text-gray-400 mt-1">
                    {(file.size / 1024).toFixed(0)} Ko
                  </p>
                  <button
                    type="button"
                    onClick={() => setFile(null)}
                    className="text-xs text-red-500 hover:underline mt-2"
                  >
                    Supprimer
                  </button>
                </div>
              ) : (
                <div>
                  <p className="text-sm text-gray-500 mb-2">
                    Glissez un fichier ou cliquez pour sélectionner
                  </p>
                  <p className="text-xs text-gray-400">PDF, DOCX, CSV, TXT · max 10 Mo</p>
                  <input
                    type="file"
                    accept=".pdf,.docx,.csv,.txt"
                    onChange={(e) => setFile(e.target.files[0])}
                    className="absolute inset-0 opacity-0 cursor-pointer"
                    style={{ position: 'relative' }}
                  />
                </div>
              )}
            </div>
            {!file && (
              <input
                type="file"
                accept=".pdf,.docx,.csv,.txt"
                onChange={(e) => setFile(e.target.files[0])}
                className="mt-2 w-full text-xs text-gray-500"
              />
            )}
          </div>
        )}

        {/* Masquage RGPD */}
        <div className="p-4 bg-blue-50 rounded-xl border border-light">
          <MaskingToggle
            enabled={form.apply_masking}
            onChange={handleMaskingChange}
          />
        </div>

        <button
          type="submit"
          disabled={loading || (mode === 'file' && !file)}
          className="w-full bg-secondary text-white py-3 rounded-xl text-sm font-medium hover:bg-primary transition-colors disabled:opacity-50"
        >
          {loading ? 'Analyse en cours...' : '⚡ Analyser et créer la procédure'}
        </button>
      </form>
    </div>
  )
}
