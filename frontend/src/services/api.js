import axios from 'axios'

const BASE = '/api'

const api = axios.create({ baseURL: BASE, timeout: 300_000 })

// ── Attach JWT on every request ────────────────────────
api.interceptors.request.use(config => {
  const token = localStorage.getItem('cim_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// ── 401 → clear token and reload to login page ─────────
api.interceptors.response.use(
  res => res,
  err => {
    if (err?.response?.status === 401) {
      localStorage.removeItem('cim_token')
      localStorage.removeItem('cim_user')
      localStorage.removeItem('cim_session_id')
      // Notify the app to show the login screen
      window.dispatchEvent(new Event('cim:unauthorized'))
    }
    return Promise.reject(err)
  }
)

// ── Auth ───────────────────────────────────────────────
export const registerUser = (email, name, password) =>
  api.post('/auth/register', { email, name, password }).then(r => r.data)

export const loginUser = (email, password) =>
  api.post('/auth/login', { email, password }).then(r => r.data)

export const getMe = () => api.get('/auth/me').then(r => r.data)

// ── Config ─────────────────────────────────────────────
export const getConfig    = ()        => api.get('/config').then(r => r.data)
export const updateConfig = (body)    => api.put('/config', body).then(r => r.data)

// ── Sessions ───────────────────────────────────────────
export const createSession  = ()    => api.post('/sessions').then(r => r.data)
export const getSession     = (id)  => api.get(`/sessions/${id}`).then(r => r.data)
export const deleteSession  = (id)  => api.delete(`/sessions/${id}`).then(r => r.data)
export const listMySessions = ()    => api.get('/sessions').then(r => r.data)

// ── Documents ──────────────────────────────────────────
export const uploadDocuments = (sessionId, files) => {
  const form = new FormData()
  files.forEach(f => form.append('files', f))
  return api.post(`/sessions/${sessionId}/documents`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 600_000,
  }).then(r => r.data)
}

export const processDocuments  = (id) => api.post(`/sessions/${id}/process`).then(r => r.data)
export const getProcessStatus  = (id) => api.get(`/sessions/${id}/process/status`).then(r => r.data)

// ── Sections ───────────────────────────────────────────
export const getAllSections     = (id)            => api.get(`/sessions/${id}/sections`).then(r => r.data)
export const getSection         = (id, name)      => api.get(`/sessions/${id}/sections/${name}`).then(r => r.data)
export const updateSection      = (id, name, content) => api.put(`/sessions/${id}/sections/${name}`, { content }).then(r => r.data)
export const generateSection    = (id, name)      => api.post(`/sessions/${id}/sections/${name}/generate`).then(r => r.data)
export const generateAllSections = (id, sections) =>
  api.post(`/sessions/${id}/generate-all`, { sections: sections || null }).then(r => r.data)
export const getGenerationStatus = (id) => api.get(`/sessions/${id}/generate-all/status`).then(r => r.data)

// ── Chat ───────────────────────────────────────────────
export const chat           = (id, message) => api.post(`/sessions/${id}/chat`, { message }).then(r => r.data)
export const getChatHistory = (id)          => api.get(`/sessions/${id}/chat/history`).then(r => r.data)

// ── PDF ────────────────────────────────────────────────
export const generatePDF    = (id) => api.post(`/sessions/${id}/generate-pdf`).then(r => r.data)
export const getPDFStatus   = (id) => api.get(`/sessions/${id}/generate-pdf/status`).then(r => r.data)
export const downloadPDFUrl = (id) => {
  const token = localStorage.getItem('cim_token')
  return `${BASE}/sessions/${id}/download-pdf?token=${token}`
}
