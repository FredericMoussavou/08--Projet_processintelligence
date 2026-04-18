import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/api'
import useAuthStore from '../store/authStore'

const GLOBAL_ROLES = [
  { value: 'admin',    label: 'Administrateur' },
  { value: 'director', label: 'Directeur' },
  { value: 'manager',  label: 'Manager' },
  { value: 'viewer',   label: 'Lecteur' },
]

const SERVICE_ROLES = [
  { value: 'service_manager', label: 'Responsable de service' },
  { value: 'service_viewer',  label: 'Membre du service' },
]

export default function AdminPage() {
  const { currentOrg, hasRole } = useAuthStore()

  const [members,      setMembers]      = useState([])
  const [services,     setServices]     = useState([])
  const [loading,      setLoading]      = useState(true)
  const [activeTab,    setActiveTab]    = useState('members')
  const [inviteForm,   setInviteForm]   = useState({ username: '', role: 'viewer' })
  const [serviceForm,  setServiceForm]  = useState({ username: '', service: '', role: 'service_viewer' })
  const [newService,   setNewService]   = useState('')
  const [error,        setError]        = useState('')
  const [success,      setSuccess]      = useState('')

  const isAdmin = hasRole(['admin'])

  const load = async () => {
    if (!currentOrg) return
    setLoading(true)
    try {
      const [membersRes, servicesRes] = await Promise.all([
        api.get(`/organizations/${currentOrg.id}/members/`),
        api.get(`/organizations/${currentOrg.id}/services/`),
      ])
      setMembers(membersRes.data.members || [])
      setServices(servicesRes.data.services || [])
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [currentOrg])

  const handleInvite = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    try {
      await api.post(`/organizations/${currentOrg.id}/members/add/`, inviteForm)
      setSuccess('Membre ajouté avec succès')
      setInviteForm({ username: '', role: 'viewer' })
      load()
    } catch (err) {
      setError(err.response?.data?.error || 'Erreur lors de l\'ajout')
    }
  }

  const handleAssignService = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    try {
      await api.post(`/organizations/${currentOrg.id}/service-members/`, serviceForm)
      setSuccess('Accès service attribué avec succès')
      setServiceForm({ username: '', service: '', role: 'service_viewer' })
      load()
    } catch (err) {
      setError(err.response?.data?.error || 'Erreur lors de l\'attribution')
    }
  }

  const handleRemoveMember = async (userId) => {
    if (!confirm('Retirer ce membre ?')) return
    try {
      await api.delete(`/organizations/${currentOrg.id}/members/${userId}/`)
      load()
    } catch (err) {
      console.error(err)
    }
  }

  const handleAddService = async (e) => {
    e.preventDefault()
    if (!newService.trim()) return
    try {
      await api.post(`/organizations/${currentOrg.id}/services/add/`, { name: newService })
      setNewService('')
      load()
    } catch (err) {
      setError(err.response?.data?.error || 'Erreur')
    }
  }

  const tabs = [
    { key: 'members',  label: `Membres (${members.length})` },
    { key: 'services', label: `Services (${services.length})` },
    { key: 'invite',   label: 'Ajouter un membre' },
  ]

  if (!isAdmin) {
    return (
      <div className="p-8 text-center">
        <p className="text-gray-400 text-sm">
          Accès réservé aux administrateurs
        </p>
        <Link to="/" className="text-secondary text-sm hover:underline mt-2 inline-block">
          ← Retour
        </Link>
      </div>
    )
  }

  return (
    <div className="p-8 space-y-6">

      {/* Header */}
      <div>
        <Link to="/" className="text-xs text-gray-400 hover:text-secondary inline-block mb-2">
          ← Tableau de bord
        </Link>
        <h2 className="text-2xl font-bold text-primary">Administration</h2>
        <p className="text-gray-500 text-sm mt-1">
          {currentOrg?.name} — Gestion des membres et des accès
        </p>
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

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">
          {error}
        </div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 rounded-lg p-3 text-sm">
          {success}
        </div>
      )}

      {/* Membres */}
      {activeTab === 'members' && (
        <div className="bg-white rounded-xl border border-light overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-gray-400 text-sm">Chargement...</div>
          ) : members.length === 0 ? (
            <div className="p-8 text-center text-gray-400 text-sm">Aucun membre</div>
          ) : (
            <table className="w-full">
              <thead className="bg-background border-b border-light">
                <tr>
                  <th className="text-left text-xs font-medium text-gray-500 px-6 py-3">Membre</th>
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Rôle global</th>
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Services</th>
                  <th className="text-left text-xs font-medium text-gray-500 px-4 py-3">Depuis</th>
                  <th className="text-right text-xs font-medium text-gray-500 px-6 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-light">
                {members.map((m) => (
                  <tr key={m.user_id} className="hover:bg-background transition-colors">
                    <td className="px-6 py-4">
                      <p className="text-sm font-medium text-primary">{m.username}</p>
                      <p className="text-xs text-gray-400">{m.email}</p>
                    </td>
                    <td className="px-4 py-4">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        m.role === 'admin'    ? 'bg-purple-100 text-purple-700' :
                        m.role === 'director' ? 'bg-blue-100 text-blue-700' :
                        m.role === 'manager'  ? 'bg-green-100 text-green-700' :
                        'bg-gray-100 text-gray-600'
                      }`}>
                        {GLOBAL_ROLES.find(r => r.value === m.role)?.label || m.role}
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex flex-wrap gap-1">
                        {m.services?.length > 0 ? m.services.map((s) => (
                          <span key={s.service} className="text-xs bg-background text-gray-500 px-2 py-0.5 rounded-full">
                            {s.service}
                          </span>
                        )) : (
                          <span className="text-xs text-gray-300">—</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <span className="text-xs text-gray-400">{m.joined_at}</span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => handleRemoveMember(m.user_id)}
                        className="text-xs text-red-400 hover:text-red-600"
                      >
                        Retirer
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Services */}
      {activeTab === 'services' && (
        <div className="space-y-4">
          {/* Liste des services */}
          <div className="bg-white rounded-xl border border-light p-6">
            <h3 className="font-semibold text-primary mb-4">Services de l'organisation</h3>
            {services.length === 0 ? (
              <p className="text-gray-400 text-sm">Aucun service défini</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {services.map((svc) => (
                  <span key={svc} className="px-3 py-1.5 bg-background border border-light rounded-lg text-sm text-primary font-medium">
                    {svc}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Ajouter un service */}
          <div className="bg-white rounded-xl border border-light p-6">
            <h3 className="font-semibold text-primary mb-4">Ajouter un service</h3>
            <form onSubmit={handleAddService} className="flex gap-3">
              <input
                type="text"
                value={newService}
                onChange={(e) => setNewService(e.target.value)}
                className="flex-1 border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary"
                placeholder="Ex: Comptabilité, RH, Direction..."
                required
              />
              <button
                type="submit"
                className="px-4 py-2 bg-secondary text-white rounded-lg text-sm font-medium hover:bg-primary transition-colors"
              >
                Ajouter
              </button>
            </form>
          </div>

          {/* Attribuer accès service */}
          <div className="bg-white rounded-xl border border-light p-6">
            <h3 className="font-semibold text-primary mb-4">Attribuer un accès à un service</h3>
            <form onSubmit={handleAssignService} className="space-y-3">
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Membre</label>
                  <input
                    type="text"
                    value={serviceForm.username}
                    onChange={(e) => setServiceForm({ ...serviceForm, username: e.target.value })}
                    className="w-full border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary"
                    placeholder="username"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Service</label>
                  <select
                    value={serviceForm.service}
                    onChange={(e) => setServiceForm({ ...serviceForm, service: e.target.value })}
                    className="w-full border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary bg-white"
                    required
                  >
                    <option value="">Choisir...</option>
                    {services.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Rôle</label>
                  <select
                    value={serviceForm.role}
                    onChange={(e) => setServiceForm({ ...serviceForm, role: e.target.value })}
                    className="w-full border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary bg-white"
                  >
                    {SERVICE_ROLES.map((r) => (
                      <option key={r.value} value={r.value}>{r.label}</option>
                    ))}
                  </select>
                </div>
              </div>
              <button
                type="submit"
                className="px-4 py-2 bg-secondary text-white rounded-lg text-sm font-medium hover:bg-primary transition-colors"
              >
                Attribuer l'accès
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Ajouter un membre */}
      {activeTab === 'invite' && (
        <div className="bg-white rounded-xl border border-light p-6 max-w-lg">
          <h3 className="font-semibold text-primary mb-4">Ajouter un membre</h3>
          <form onSubmit={handleInvite} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-primary mb-1">
                Nom d'utilisateur
              </label>
              <input
                type="text"
                value={inviteForm.username}
                onChange={(e) => setInviteForm({ ...inviteForm, username: e.target.value })}
                className="w-full border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary"
                placeholder="username exact"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-primary mb-1">
                Rôle global
              </label>
              <select
                value={inviteForm.role}
                onChange={(e) => setInviteForm({ ...inviteForm, role: e.target.value })}
                className="w-full border border-light rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-secondary bg-white"
              >
                {GLOBAL_ROLES.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </div>
            <button
              type="submit"
              className="w-full bg-secondary text-white py-2 rounded-lg text-sm font-medium hover:bg-primary transition-colors"
            >
              Ajouter le membre
            </button>
          </form>
        </div>
      )}
    </div>
  )
}