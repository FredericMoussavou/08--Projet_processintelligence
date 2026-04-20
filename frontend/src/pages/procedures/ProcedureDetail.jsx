import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { proceduresAPI, changeRequestsAPI } from '../../services/api'
import useAuthStore from '../../store/authStore'
import FeatureLock from '../../components/ui/FeatureLock'

function ScoreBar({ score, label, color }) {
  const pct = Math.round(score * 100)
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

function SeverityBadge({ severity }) {
  const styles = {
    blocking: 'bg-red-100 text-red-700',
    warning : 'bg-yellow-100 text-yellow-700',
    info    : 'bg-blue-100 text-blue-700',
  }
  const labels = {
    blocking: 'Bloquant',
    warning : 'Avertissement',
    info    : 'Info',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${styles[severity] || styles.info}`}>
      {labels[severity] || severity}
    </span>
  )
}

function ComplianceBadge({ status }) {
  const styles = {
    compliant    : 'bg-green-100 text-green-700',
    warning      : 'bg-yellow-100 text-yellow-700',
    non_compliant: 'bg-red-100 text-red-700',
  }
  const labels = {
    compliant    : 'Conforme',
    warning      : 'À vérifier',
    non_compliant: 'Non conforme',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${styles[status] || styles.warning}`}>
      {labels[status] || status}
    </span>
  )
}

export default function ProcedureDetail() {
  const { id }       = useParams()
  const navigate     = useNavigate()
  const { currentOrg, canApprove } = useAuthStore()

  const [procedure,   setProcedure]   = useState(null)
  const [report,      setReport]      = useState(null)
  const [history,     setHistory]     = useState([])
  const [activeTab,   setActiveTab]   = useState('overview')
  const [loading,     setLoading]     = useState(true)
  const [crForm,      setCrForm]      = useState({ description: '', change_type: 'patch' })
  const [crLoading,   setCrLoading]   = useState(false)
  const [crSuccess,   setCrSuccess]   = useState(null)
  const [crError,     setCrError]     = useState('')
  const [analyzing,   setAnalyzing]   = useState(false)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const [detailRes, histRes] = await Promise.all([
          proceduresAPI.detail(id),
          proceduresAPI.history(id),
        ])
        setProcedure(detailRes.data)
        setHistory(histRes.data.history || [])
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id])

  const handleAnalyze = async () => {
    setAnalyzing(true)
    try {
      const res = await proceduresAPI.analyze(id)
      setReport(res.data)
    } catch (err) {
      console.error(err)
    } finally {
      setAnalyzing(false)
    }
  }

  const handleExportPdf = async () => {
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

  const handleExportBpmn = async () => {
    try {
      const res = await proceduresAPI.exportBpmn(id)
      const url = URL.createObjectURL(new Blob([res.data]))
      const a   = document.createElement('a')
      a.href    = url
      a.download = `procedure_${id}.bpmn`
      a.click()
    } catch (err) {
      console.error(err)
    }
  }

  const handleSubmitCR = async (e) => {
    e.preventDefault()
    setCrLoading(true)
    setCrError('')
    setCrSuccess(null)
    try {
      const res = await changeRequestsAPI.submit({
        procedure_id: parseInt(id),
        ...crForm,
      })
      setCrSuccess(res.data)
      setCrForm({ description: '', change_type: 'patch' })
    } catch (err) {
      setCrError(err.response?.data?.error || 'Erreur lors de la soumission')
    } finally {
      setCrLoading(false)
    }
  }

  const handleArchive = async () => {
    if (!confirm('Archiver cette procédure ?')) return
    try {
      await proceduresAPI.archive(id, { change_summary: 'Archivage manuel' })
      navigate('/procedures')
    } catch (err) {
      console.error(err)
    }
  }

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center h-64">
        <div className="text-gray-400 text-sm">Chargement...</div>
      </div>
    )
  }

  if (!procedure) {
    return (
      <div className="p-8 text-center">
        <p className="text-gray-400">Procédure introuvable</p>
        <Link to="/procedures" className="text-secondary text-sm hover:underline mt-2 inline-block">
          ← Retour
        </Link>
      </div>
    )
  }

  const tabs = [
    { key: 'overview',   label: 'Vue générale' },
    { key: 'steps',    label: `Étapes (${procedure?.steps_count || 0})` },
    { key: 'audit',      label: 'Audit' },
    { key: 'history',    label: `Historique (${history.length})` },
    { key: 'changes',    label: 'Demande de changement' },
  ]

  return (
    <div className="p-8 space-y-6">

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Link to="/procedures" className="text-xs text-gray-400 hover:text-secondary mb-2 inline-block">
            ← Procédures
          </Link>
          <h2 className="text-2xl font-bold text-primary">{procedure.title}</h2>
          <div className="flex items-center gap-3 mt-2">
            <span className="text-sm text-gray-500">{procedure.service || 'Sans service'}</span>
            <span className="text-gray-300">·</span>
            <span className="text-sm font-mono text-gray-500">v{procedure.version}</span>
            <span className="text-gray-300">·</span>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              procedure.status === 'active'   ? 'bg-green-100 text-green-700' :
              procedure.status === 'archived' ? 'bg-gray-100 text-gray-500' :
              'bg-yellow-100 text-yellow-700'
            }`}>
              {procedure.status === 'active' ? 'Active' : procedure.status === 'archived' ? 'Archivée' : 'Brouillon'}
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <button
            onClick={handleAnalyze}
            disabled={analyzing}
            className="px-4 py-2 bg-secondary text-white rounded-lg text-sm font-medium hover:bg-primary transition-colors disabled:opacity-50"
          >
            {analyzing ? 'Analyse...' : '⚡ Analyser'}
          </button>
          <button
            onClick={handleExportPdf}
            className="px-4 py-2 bg-white border border-light text-primary rounded-lg text-sm hover:bg-background transition-colors"
          >
            PDF
          </button>
          <FeatureLock feature="export_bpmn" requiredPlan="Pro">
            <button
              onClick={handleExportBpmn}
              className="px-4 py-2 bg-white border border-light text-primary rounded-lg text-sm hover:bg-background transition-colors"
            >
              BPMN
            </button>
          </FeatureLock>
          {procedure.status !== 'archived' && canApprove() && (
            <button
              onClick={handleArchive}
              className="px-4 py-2 bg-white border border-light text-gray-500 rounded-lg text-sm hover:bg-background transition-colors"
            >
              Archiver
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-light">
        <div className="flex gap-6">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? 'border-secondary text-secondary'
                  : 'border-transparent text-gray-500 hover:text-primary'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      {activeTab === 'overview' && (
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-light p-6">
            <h3 className="font-semibold text-primary mb-4">Informations</h3>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-gray-400 text-xs mb-1">Service</p>
                <p className="font-medium">{procedure.service || '—'}</p>
              </div>
              <div>
                <p className="text-gray-400 text-xs mb-1">Version</p>
                <p className="font-medium font-mono">v{procedure.version}</p>
              </div>
              <div>
                <p className="text-gray-400 text-xs mb-1">Créée le</p>
                <p className="font-medium">{procedure.created_at}</p>
              </div>
              <div>
                <p className="text-gray-400 text-xs mb-1">Mise à jour</p>
                <p className="font-medium">{procedure.updated_at}</p>
              </div>
              {procedure.archived_at && (
                <div>
                  <p className="text-gray-400 text-xs mb-1">Archivée le</p>
                  <p className="font-medium">{procedure.archived_at}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'steps' && (
        <div className="space-y-3">
          {/* Barre d'actions */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">
              {procedure.steps_count} étape{procedure.steps_count > 1 ? 's' : ''}
            </p>
            <div className="flex gap-2">
              <button
                onClick={handleExportPdf}
                className="px-3 py-1.5 bg-white border border-light text-primary rounded-lg text-xs hover:bg-background transition-colors"
              >
                Télécharger PDF
              </button>
              <FeatureLock feature="export_bpmn" requiredPlan="Pro">
                <button
                  onClick={handleExportBpmn}
                  className="px-3 py-1.5 bg-white border border-light text-primary rounded-lg text-xs hover:bg-background transition-colors"
                >
                  Télécharger BPMN
                </button>
              </FeatureLock>
            </div>
          </div>

          {/* Étapes */}
          {procedure.steps?.length === 0 ? (
            <div className="bg-white rounded-xl border border-light p-12 text-center">
              <p className="text-gray-400 text-sm">Aucune étape enregistrée</p>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-light overflow-hidden">
              {procedure.steps?.map((step, index) => (
                <div
                  key={step.id}
                  className={`p-5 ${index < procedure.steps.length - 1 ? 'border-b border-light' : ''}`}
                >
                  <div className="flex items-start gap-4">
                    {/* Numéro */}
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-secondary/10 flex items-center justify-center">
                      <span className="text-xs font-bold text-secondary">{step.order}</span>
                    </div>

                    {/* Contenu */}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-primary">{step.title}</p>

                      {/* Métadonnées */}
                      <div className="flex flex-wrap gap-3 mt-2">
                        {step.actor_role && (
                          <span className="flex items-center gap-1 text-xs text-gray-500">
                            <span className="text-gray-300">Acteur</span>
                            <span className="font-medium text-primary">{step.actor_role}</span>
                          </span>
                        )}
                        {step.action_verb && (
                          <span className="flex items-center gap-1 text-xs text-gray-500">
                            <span className="text-gray-300">Verbe</span>
                            <span className="font-medium text-secondary">{step.action_verb}</span>
                          </span>
                        )}
                        {step.tool_used && (
                          <span className="flex items-center gap-1 text-xs text-gray-500">
                            <span className="text-gray-300">Outil</span>
                            <span className="font-medium text-primary">{step.tool_used}</span>
                          </span>
                        )}
                        {step.estimated_duration > 0 && (
                          <span className="text-xs text-gray-400">
                            {step.estimated_duration} min
                          </span>
                        )}
                      </div>

                      {/* Tags */}
                      <div className="flex flex-wrap gap-2 mt-2">
                        <span className="text-xs bg-background text-gray-500 px-2 py-0.5 rounded-full">
                          {step.output_type}
                        </span>
                        <span className="text-xs bg-background text-gray-500 px-2 py-0.5 rounded-full">
                          {step.trigger_type}
                        </span>
                        {step.is_recurring && (
                          <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">
                            Récurrent
                          </span>
                        )}
                        {step.has_condition && (
                          <span className="text-xs bg-yellow-50 text-yellow-600 px-2 py-0.5 rounded-full">
                            Condition
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Score + conformité */}
                    <div className="flex-shrink-0 text-right space-y-1">
                      <div>
                        <p className="text-xs text-gray-400">Auto.</p>
                        <p className={`text-sm font-bold ${
                          step.automation_score >= 0.7 ? 'text-green-600' :
                          step.automation_score >= 0.4 ? 'text-orange-500' :
                          'text-red-500'
                        }`}>
                          {Math.round(step.automation_score * 100)}%
                        </p>
                      </div>
                      <ComplianceBadge status={
                        step.compliance_status === 'Conforme' ? 'compliant' :
                        step.compliance_status === 'À vérifier' ? 'warning' : 'non_compliant'
                      } />
                    </div>
                  </div>

                  {/* Connecteur visuel */}
                  {index < procedure.steps.length - 1 && (
                    <div className="ml-4 mt-3 flex items-center gap-2">
                      <div className="w-0.5 h-4 bg-light ml-3.5"/>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === 'audit' && (
        <div className="space-y-4">
          {!report ? (
            <div className="bg-white rounded-xl border border-light p-12 text-center">
              <p className="text-gray-400 text-sm mb-4">
                Aucun rapport d'audit disponible
              </p>
              <button
                onClick={handleAnalyze}
                disabled={analyzing}
                className="px-6 py-2 bg-secondary text-white rounded-lg text-sm font-medium hover:bg-primary transition-colors disabled:opacity-50"
              >
                {analyzing ? 'Analyse en cours...' : '⚡ Lancer l\'analyse'}
              </button>
            </div>
          ) : (
            <>
              {/* Scores */}
              <div className="bg-white rounded-xl border border-light p-6">
                <h3 className="font-semibold text-primary mb-4">Scores</h3>
                <div className="grid grid-cols-2 gap-6">
                  <ScoreBar
                    score={report.scores?.optimization || 0}
                    label="Score d'optimisation"
                    color={report.scores?.optimization >= 0.7 ? '#1E7A4A' : report.scores?.optimization >= 0.4 ? '#C76B00' : '#CC0000'}
                  />
                  <ScoreBar
                    score={report.scores?.automation || 0}
                    label="Score d'automatisation"
                    color={report.scores?.automation >= 0.7 ? '#1E7A4A' : report.scores?.automation >= 0.4 ? '#C76B00' : '#CC0000'}
                  />
                </div>
              </div>

              {/* Anomalies */}
              {report.anomalies?.length > 0 && (
                <div className="bg-white rounded-xl border border-light p-6">
                  <h3 className="font-semibold text-primary mb-4">
                    Anomalies ({report.anomalies.length})
                  </h3>
                  <div className="space-y-3">
                    {report.anomalies.map((a, i) => (
                      <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-background">
                        <SeverityBadge severity={a.severity} />
                        <p className="text-sm text-gray-600 flex-1">{a.description}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommandations */}
              {report.recommendations?.length > 0 && (
                <div className="bg-white rounded-xl border border-light p-6">
                  <h3 className="font-semibold text-primary mb-4">
                    Recommandations ({report.recommendations.length})
                  </h3>
                  <div className="space-y-3">
                    {report.recommendations.map((r, i) => (
                      <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-background">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0 ${
                          r.priority === 'high'   ? 'bg-red-100 text-red-700' :
                          r.priority === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                          'bg-green-100 text-green-700'
                        }`}>
                          {r.priority === 'high' ? 'Haute' : r.priority === 'medium' ? 'Moyenne' : 'Faible'}
                        </span>
                        <p className="text-sm text-gray-600 flex-1">{r.action}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {activeTab === 'history' && (
        <div className="bg-white rounded-xl border border-light p-6">
          <h3 className="font-semibold text-primary mb-4">Historique des versions</h3>
          {history.length === 0 ? (
            <p className="text-gray-400 text-sm text-center py-8">
              Aucun historique disponible
            </p>
          ) : (
            <div className="space-y-3">
              {history.map((v, i) => (
                <div key={i} className="flex items-start gap-4 p-4 rounded-lg bg-background">
                  <div className="flex-shrink-0">
                    <span className="text-sm font-mono font-bold text-primary">
                      v{v.version_number}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs bg-secondary/10 text-secondary px-2 py-0.5 rounded-full">
                        {v.reason}
                      </span>
                      <span className="text-xs text-gray-400">{v.created_at}</span>
                    </div>
                    {v.change_summary && (
                      <p className="text-sm text-gray-600">{v.change_summary}</p>
                    )}
                    <p className="text-xs text-gray-400 mt-1">
                      {v.steps_count} étape{v.steps_count > 1 ? 's' : ''} · par {v.created_by}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === 'changes' && (
        <div className="space-y-4">

          {/* Résultat de la dernière soumission */}
          {crSuccess && (
            <div className="bg-green-50 border border-green-200 rounded-xl p-4">
              <p className="text-sm font-medium text-green-700 mb-1">
                Demande soumise avec succès
              </p>
              <p className="text-sm text-green-600">{crSuccess.location || crSuccess.message}</p>
              {crSuccess.blocking_rules?.length > 0 && (
                <div className="mt-3 space-y-2">
                  <p className="text-xs font-medium text-red-600">Règles bloquantes :</p>
                  {crSuccess.blocking_rules.map((r, i) => (
                    <div key={i} className="text-xs text-red-600 bg-red-50 p-2 rounded">
                      {r.label} — {r.legal_ref}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Formulaire */}
          <div className="bg-white rounded-xl border border-light p-6">
            <h3 className="font-semibold text-primary mb-4">
              Soumettre une demande de changement
            </h3>

            {crError && (
              <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-4 text-sm">
                {crError}
              </div>
            )}

            <form onSubmit={handleSubmitCR} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-primary mb-1">
                  Type de changement
                </label>
                <select
                  value={crForm.change_type}
                  onChange={(e) => setCrForm({ ...crForm, change_type: e.target.value })}
                  className="w-full border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary bg-white"
                >
                  <option value="patch">Correctif (patch) — v1.0 → v1.1</option>
                  <option value="minor">Mineur — ajout d'étape, modification acteur</option>
                  <option value="major">Majeur — refonte structurelle</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-primary mb-1">
                  Description du changement
                </label>
                <textarea
                  value={crForm.description}
                  onChange={(e) => setCrForm({ ...crForm, description: e.target.value })}
                  className="w-full border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary"
                  rows={4}
                  placeholder="Décrivez les modifications souhaitées..."
                  required
                />
              </div>

              <button
                type="submit"
                disabled={crLoading}
                className="px-6 py-2 bg-secondary text-white rounded-lg text-sm font-medium hover:bg-primary transition-colors disabled:opacity-50"
              >
                {crLoading ? 'Soumission...' : 'Soumettre la demande'}
              </button>
            </form>
          </div>
        </div>
      )}

    </div>
  )
}
