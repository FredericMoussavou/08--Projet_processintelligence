import axios from 'axios'

const API_BASE = 'http://127.0.0.1:8000/api'

// Instance axios avec config de base
const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Intercepteur — ajoute le token JWT à chaque requête
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Intercepteur — gère l'expiration du token
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config

    if (error.response?.status === 401 && !original._retry) {
      original._retry = true

      try {
        const refresh = localStorage.getItem('refresh_token')
        const res = await axios.post(`${API_BASE}/auth/refresh/`, { refresh })
        const newToken = res.data.access

        localStorage.setItem('access_token', newToken)
        original.headers.Authorization = `Bearer ${newToken}`

        return api(original)
      } catch {
        // Refresh expiré — déconnexion
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        window.location.href = '/login'
      }
    }

    return Promise.reject(error)
  }
)

// ─── Auth ───────────────────────────────────────────
export const authAPI = {
  login: (credentials) =>
    api.post('/auth/login/', credentials),

  register: (data) =>
    api.post('/auth/register/', data),

  me: () =>
    api.get('/auth/me/'),

  refresh: (refresh) =>
    api.post('/auth/refresh/', { refresh }),
}

// ─── Procédures ─────────────────────────────────────
export const proceduresAPI = {
  list: (orgId, params = {}) =>
    api.get(`/procedures/list/${orgId}/`, { params }),

  ingest: (data) =>
    api.post('/procedures/ingest/', data),

  ingestFile: (formData) =>
    api.post('/procedures/ingest/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }),

  analyze: (id) =>
    api.post(`/procedures/${id}/analyze/`),

  compliance: (id) =>
    api.get(`/procedures/${id}/compliance/`),

  exportPdf: (id) =>
    api.get(`/procedures/${id}/export/pdf/`, { responseType: 'blob' }),

  exportBpmn: (id) =>
    api.get(`/procedures/${id}/export/bpmn/`, { responseType: 'blob' }),

  history: (id) =>
    api.get(`/procedures/${id}/history/`),

  archive: (id, data) =>
    api.post(`/procedures/${id}/archive/`, data),

  csvTemplate: () =>
    api.get('/procedures/template/csv/', { responseType: 'blob' }),

  detail: (id) =>
    api.get(`/procedures/${id}/`),
}

// ─── Manuel ─────────────────────────────────────────
export const manualAPI = {
  generate: (orgId, params = {}) =>
    api.get(`/procedures/manual/${orgId}/`, {
      params,
      responseType: 'blob'
    }),
}

// ─── Conformité ─────────────────────────────────────
export const complianceAPI = {
  check: (id) =>
    api.post(`/procedures/${id}/compliance/`),

  rules: (sector) =>
    api.get('/procedures/rules/', { params: { sector } }),
}

// ─── Change Requests ────────────────────────────────
export const changeRequestsAPI = {
  list: (params = {}) =>
    api.get('/procedures/change-requests/', { params }),

  submit: (data) =>
    api.post('/procedures/change-requests/', data),

  status: (id) =>
    api.get(`/procedures/change-requests/${id}/`),

  approve: (id, data) =>
    api.post(`/procedures/change-requests/${id}/approve/`, data),

  reject: (id, data) =>
    api.post(`/procedures/change-requests/${id}/reject/`, data),
}

// ─── Organisations ──────────────────────────────────
export const organizationsAPI = {
  theme: (slug) =>
    api.get(`/organizations/${slug}/theme/`),
}

export default api