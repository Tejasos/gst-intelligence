import axios from 'axios'

export const getApiBase = () => {
  let base = ''
  if (typeof window !== 'undefined') {
    const custom = localStorage.getItem('gst_backend_url')
    if (custom && custom.trim()) {
      base = custom.trim().replace(/\/+$/, '')
    }
  }
  if (!base) {
    base = (import.meta.env.VITE_API_URL || '/api').trim().replace(/\/+$/, '')
  }
  // Automatically normalize http/https hostnames so /api is always the base
  if (/^https?:\/\//i.test(base) && !base.endsWith('/api') && !base.includes('/api/')) {
    base = `${base}/api`
  }
  return base
}

export const setApiBase = (url) => {
  if (typeof window !== 'undefined') {
    if (url && url.trim()) {
      let clean = url.trim().replace(/\/+$/, '')
      if (!clean.endsWith('/api') && !clean.includes('/api/')) {
        clean = `${clean}/api`
      }
      localStorage.setItem('gst_backend_url', clean)
    } else {
      localStorage.removeItem('gst_backend_url')
    }
    // Dispatch event for UI reactivity
    window.dispatchEvent(new CustomEvent('gst-backend-url-changed', { detail: getApiBase() }))
  }
}

const api = axios.create({
  timeout: 120000,
})

// Attach base URL and token/guest headers dynamically
api.interceptors.request.use((config) => {
  config.baseURL = getApiBase()
  
  const token = localStorage.getItem('gst_auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  } else {
    let guestId = localStorage.getItem('gst_guest_id')
    if (!guestId) {
      guestId = 'guest_' + Math.random().toString(36).substring(2, 12)
      localStorage.setItem('gst_guest_id', guestId)
    }
    config.headers['X-Guest-ID'] = guestId
  }
  return config
})

// Intercept responses to detect 404 or backend disconnects
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 404 || error.code === 'ERR_NETWORK') {
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('gst-backend-disconnected', { detail: error }))
      }
    }
    return Promise.reject(error)
  }
)

// ── Auth ──────────────────────────────────────────────────────────────────────

export const loginApi = (email, password) => api.post('/auth/login', { email, password })
export const registerApi = (username, email, password) => api.post('/auth/register', { username, email, password })
export const logoutApi = () => api.post('/auth/logout')
export const getMeApi = () => api.get('/auth/me')
export const getAiStatusApi = () => api.get('/ai/status')

// ── Upload ────────────────────────────────────────────────────────────────────

export const uploadPDF = (file, onProgress) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded * 100) / e.total))
    },
  })
}

export const getFiles = () => api.get('/files')
export const activateFile = (fileId) => api.post(`/files/${fileId}/activate`)
export const resetSession = () => api.delete('/session')

// ── Chat ──────────────────────────────────────────────────────────────────────

export const sendChat = (query, fileId) =>
  api.post('/chat', { query, file_id: fileId })

export const getChatHistory = () => api.get('/chat/history')
export const clearChatHistory = () => api.delete('/chat/history')

/**
 * Stream chat response via fetch + ReadableStream.
 * onToken(token, isDirect) — called for each streamed token
 * onDone()                 — called when streaming completes
 * onError(err)             — called on error
 */
export const streamChat = async (query, fileId, onToken, onDone, onError) => {
  try {
    const token = localStorage.getItem('gst_auth_token')
    const headers = { 'Content-Type': 'application/json' }
    if (token) {
      headers.Authorization = `Bearer ${token}`
    } else {
      const guestId = localStorage.getItem('gst_guest_id')
      if (guestId) headers['X-Guest-ID'] = guestId
    }

    const response = await fetch(`${getApiBase()}/chat/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ query, file_id: fileId }),
    })

    if (!response.ok) {
      throw new Error(`Chat stream failed (HTTP ${response.status})`)
    }

    const reader  = response.body.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const text  = decoder.decode(value, { stream: true })
      const lines = text.split('\n').filter((l) => l.startsWith('data: '))

      for (const line of lines) {
        try {
          const data = JSON.parse(line.slice(6))
          if (data.token) onToken(data.token, !!data.direct)
          if (data.done) {
            onDone()
            return
          }
        } catch (_) {
          // ignore malformed JSON
        }
      }
    }
    onDone()
  } catch (err) {
    if (onError) onError(err)
  }
}

// ── Analytics ─────────────────────────────────────────────────────────────────

export const getAnalytics     = ()       => api.get('/analytics')
export const getAnalyticsById = (fileId) => api.get(`/analytics/${fileId}`)

// ── Reconciliation ────────────────────────────────────────────────────────────

export const getAllReconciliations   = ()       => api.get('/reconciliation')
export const getReconciliationByPeriod = (period) =>
  api.get(`/reconciliation/${encodeURIComponent(period)}`)
export const computeReconciliation  = (gstr1Id, gstr3bId) =>
  api.post('/reconciliation/compute', { gstr1_file_id: gstr1Id, gstr3b_file_id: gstr3bId })

// ── Export ────────────────────────────────────────────────────────────────────

export const exportExcel = (fileId) => window.open(`${getApiBase()}/export/excel/${fileId}`, '_blank')
export const exportPDF   = (fileId) => window.open(`${getApiBase()}/export/pdf/${fileId}`,   '_blank')
export const exportActiveExcel = () => window.open(`${getApiBase()}/export/active/excel`, '_blank')
export const exportActivePDF   = () => window.open(`${getApiBase()}/export/active/pdf`,   '_blank')

// MOM export — format: 'raw' | 'l' | 'cr', optional annualFileId
export const exportMOMExcel = (fmt = 'raw', annualFileId = null) => {
  const params = new URLSearchParams({ format: fmt })
  if (annualFileId) params.append('annual_file_id', annualFileId)
  window.open(`${getApiBase()}/export/mom/excel?${params}`, '_blank')
}

// GSTR-3B MOM export — 52-column format matching official reference
export const exportMOM3BExcel = (fmt = 'raw', annualFileId = null) => {
  const params = new URLSearchParams({ format: fmt })
  if (annualFileId) params.append('annual_file_id', annualFileId)
  window.open(`${getApiBase()}/export/mom-3b/excel?${params}`, '_blank')
}

// GSTR-9 export — exact reference format (one sheet per year)
export const exportMOM9Excel = (fmt = 'raw') => {
  const params = new URLSearchParams({ format: fmt })
  window.open(`${getApiBase()}/export/mom-9/excel?${params}`, '_blank')
}

// ── GSTR-2B Compiler ─────────────────────────────────────────────────────────

/**
 * Upload multiple GSTR-2B .xlsx files and receive the compiled workbook.
 * Returns a Blob URL the caller can use to trigger a download.
 */
export const compileGSTR2B = async (files, onProgress) => {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))

  const response = await fetch(`${getApiBase()}/gstr2b/compile`, {
    method: 'POST',
    body: form,
  })

  if (!response.ok) {
    const err = await response.json().catch(() => ({ error: response.statusText }))
    throw new Error(err.error || 'Compilation failed')
  }

  const blob = await response.blob()
  const url  = URL.createObjectURL(blob)

  // Extract filename from Content-Disposition header
  const cd   = response.headers.get('Content-Disposition') || ''
  const match = cd.match(/filename="?([^"]+)"?/)
  const name  = match ? match[1] : 'GSTR2B_Compiled.xlsx'

  return { url, name }
}

// ── GSTR-2A Compiler ─────────────────────────────────────────────────────────

/**
 * Upload multiple GSTR-2A .xlsx files and receive the compiled workbook.
 * Returns a Blob URL the caller can use to trigger a download.
 */
export const compileGSTR2A = async (files, onProgress) => {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))

  const response = await fetch(`${getApiBase()}/gstr2a/compile`, {
    method: 'POST',
    body: form,
  })

  if (!response.ok) {
    const err = await response.json().catch(() => ({ error: response.statusText }))
    throw new Error(err.error || 'Compilation failed')
  }

  const blob = await response.blob()
  const url  = URL.createObjectURL(blob)

  const cd    = response.headers.get('Content-Disposition') || ''
  const match = cd.match(/filename="?([^"]+)"?/)
  const name  = match ? match[1] : 'GSTR2A_Compiled.xlsx'

  return { url, name }
}

// ── Risk Intelligence ─────────────────────────────────────────────────────────

export const getRiskRatios   = () => api.get('/intelligence/ratios')
export const getAnomalies    = () => api.get('/intelligence/anomalies')
export const exportRiskExcel = () => window.open(`${getApiBase()}/export/risk/excel`, '_blank')
export const exportAnomaliesExcel = () => window.open(`${getApiBase()}/export/anomalies/excel`, '_blank')

export default api
