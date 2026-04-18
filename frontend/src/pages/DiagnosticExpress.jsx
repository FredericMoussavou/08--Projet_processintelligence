import { useState } from 'react'
import { Link } from 'react-router-dom'
import axios from 'axios'

const API_BASE = 'http://127.0.0.1:8000/api'

function ScoreBar({ score, label }) {
  const pct   = Math.round(score * 100)
  const color = pct >= 70 ? '#1E7A4A' : pct >= 40 ? '#C76B00' : '#CC0000'
  return (
    <div>
      <div className="flex justify-between items-center mb-1">
        <span className="text-xs text-gray-500">{label}</span>
        <span className="text-sm font-bold" style={{ color }}>{pct}%</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
    </div>
  )
}

export default function DiagnosticExpress() {
  const [text,    setText]    = useState('')
  const [loading, setLoading] = useState(false)
  const [result,  setResult]  = useState(null)
  const [error,   setError]   = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    setResult(null)

    try {
      // Ingestion sans authentification
      const res = await axios.post(`${API_BASE}/procedures/ingest/`, {
        text,
        title          : 'Diagnostic Express',
        organization_id: 1,
        apply_masking  : true,
      })

      setResult(res.data)
    } catch (err) {
      setError(err.response?.data?.error || 'Erreur lors de l\'analyse')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background">

      {/* Header */}
      <header className="bg-white border-b border-light px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-primary">ProcessIntelligence</h1>
            <p className="text-xs text-gray-400">Diagnostic Express</p>
          </div>
          <div className="flex gap-3">
            <Link
              to="/login"
              className="px-4 py-2 text-sm text-secondary hover:underline font-medium"
            >
              Se connecter
            </Link>
            <Link
              to="/register"
              className="px-4 py-2 bg-secondary text-white rounded-lg text-sm font-medium hover:bg-primary transition-colors"
            >
              Créer un compte
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-12 space-y-10">

        {/* Hero */}
        <div className="text-center space-y-4">
          <div className="inline-block bg-blue-50 text-secondary text-xs font-medium px-3 py-1 rounded-full border border-light">
            Gratuit · Sans inscription · Résultat en 60 secondes
          </div>
          <h2 className="text-4xl font-bold text-primary leading-tight">
            Analysez votre procédure<br />
            <span className="text-secondary">en quelques secondes</span>
          </h2>
          <p className="text-gray-500 max-w-xl mx-auto">
            Décrivez votre procédure en langage naturel. Notre IA identifie
            les dysfonctionnements, calcule le potentiel d'automatisation
            et génère des recommandations concrètes.
          </p>
        </div>

        {/* Formulaire */}
        {!result ? (
          <div className="bg-white rounded-2xl border border-light p-8 shadow-sm">
            <form onSubmit={handleSubmit} className="space-y-4">

              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">
                  {error}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-primary mb-2">
                  Décrivez votre procédure
                </label>
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  className="w-full border border-light rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-secondary resize-none"
                  rows={7}
                  placeholder={`Exemple :\n\nLe RH publie l'offre d'emploi sur LinkedIn. Le manager reçoit les CVs et les analyse dans Excel. Si un candidat est retenu, le RH organise un entretien. La DG valide l'embauche et signe le contrat.`}
                  required
                />
                <p className="text-xs text-gray-400 mt-1 text-right">
                  {text.length} / 50 000 caractères
                </p>
              </div>

              <div className="flex items-center gap-2 text-xs text-gray-400">
                <svg className="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
                Masquage RGPD automatique — vos données sensibles sont anonymisées avant analyse
              </div>

              <button
                type="submit"
                disabled={loading || text.length < 20}
                className="w-full bg-secondary text-white py-3 rounded-xl text-sm font-semibold hover:bg-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                    </svg>
                    Analyse en cours...
                  </span>
                ) : '⚡ Lancer le diagnostic gratuit'}
              </button>
            </form>
          </div>
        ) : (
          /* Résultat */
          <div className="space-y-6">

            {/* Header résultat */}
            <div className="bg-green-50 border border-green-200 rounded-2xl p-6 flex items-start justify-between">
              <div>
                <h3 className="font-semibold text-green-700 text-lg">
                  ✅ Diagnostic terminé
                </h3>
                <p className="text-sm text-green-600 mt-1">
                  {result.steps_count} étape{result.steps_count > 1 ? 's' : ''} analysée{result.steps_count > 1 ? 's' : ''}
                  {result.analysis?.anomalies_count > 0 && (
                    <span className="ml-2 text-orange-600">
                      · {result.analysis.anomalies_count} anomalie{result.analysis.anomalies_count > 1 ? 's' : ''} détectée{result.analysis.anomalies_count > 1 ? 's' : ''}
                    </span>
                  )}
                </p>
              </div>
              <button
                onClick={() => { setResult(null); setText('') }}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                Nouveau diagnostic
              </button>
            </div>

            {/* Scores */}
            {result.analysis && (
              <div className="bg-white rounded-2xl border border-light p-6">
                <h3 className="font-semibold text-primary mb-4">Scores</h3>
                <div className="grid grid-cols-2 gap-6">
                  <ScoreBar score={result.analysis.score_optim} label="Score d'optimisation" />
                  <ScoreBar score={result.analysis.score_auto}  label="Score d'automatisation" />
                </div>
              </div>
            )}

            {/* Étapes */}
            <div className="bg-white rounded-2xl border border-light p-6">
              <h3 className="font-semibold text-primary mb-4">
                Étapes extraites ({result.steps_count})
              </h3>
              <div className="space-y-3">
                {result.steps?.map((step) => (
                  <div key={step.order} className="flex items-start gap-3 p-3 rounded-xl bg-background">
                    <span className="w-6 h-6 rounded-full bg-secondary/10 flex items-center justify-center flex-shrink-0">
                      <span className="text-xs font-bold text-secondary">{step.order}</span>
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
                    <div className="text-right flex-shrink-0">
                      <p className={`text-sm font-bold ${
                        step.automation_score >= 0.7 ? 'text-green-600' :
                        step.automation_score >= 0.4 ? 'text-orange-500' : 'text-red-500'
                      }`}>
                        {Math.round(step.automation_score * 100)}%
                      </p>
                      <p className="text-xs text-gray-400">auto.</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* CTA — créer un compte */}
            <div className="bg-primary rounded-2xl p-8 text-center text-white">
              <h3 className="text-xl font-bold mb-2">
                Envie d'aller plus loin ?
              </h3>
              <p className="text-white/70 text-sm mb-6 max-w-md mx-auto">
                Créez un compte gratuit pour accéder au rapport d'audit complet,
                à l'export BPMN, au manuel de procédures et au workflow de validation.
              </p>
              <div className="flex gap-3 justify-center">
                <Link
                  to="/register"
                  className="px-6 py-3 bg-white text-primary rounded-xl text-sm font-semibold hover:bg-background transition-colors"
                >
                  Créer un compte gratuit
                </Link>
                <Link
                  to="/login"
                  className="px-6 py-3 bg-white/10 text-white rounded-xl text-sm font-medium hover:bg-white/20 transition-colors"
                >
                  Se connecter
                </Link>
              </div>
            </div>

          </div>
        )}

        {/* Features */}
        {!result && (
          <div className="grid grid-cols-3 gap-6">
            {[
              {
                title: 'Extraction automatique',
                desc : 'L\'IA identifie les étapes, acteurs et outils directement depuis votre texte',
              },
              {
                title: 'Scoring intelligent',
                desc : 'Score d\'optimisation et d\'automatisation calculés instantanément',
              },
              {
                title: 'Conformité légale',
                desc : 'Vérification automatique face aux réglementations de votre secteur',
              },
            ].map((f) => (
              <div key={f.title} className="bg-white rounded-xl border border-light p-5">
                <h4 className="font-semibold text-primary text-sm mb-2">{f.title}</h4>
                <p className="text-xs text-gray-500 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        )}

      </main>
    </div>
  )
}