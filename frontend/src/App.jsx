import React from 'react'
import { Routes, Route } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { AppProvider, useApp } from './context/AppContext'
import Home from './pages/Home'
import FullReport from './pages/FullReport'
import BackendConfigModal from './components/BackendConfigModal'
import { AlertTriangle, RefreshCw, Settings } from 'lucide-react'

function GlobalBackendBanner() {
  const { backendStatus, backendError, setShowBackendModal, checkBackendHealth } = useApp()
  const customUrl = typeof window !== 'undefined' ? localStorage.getItem('gst_backend_url') : null

  if (backendStatus !== 'disconnected') return null

  const handleUseServerless = () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('gst_backend_url')
      window.dispatchEvent(new CustomEvent('gst-backend-url-changed', { detail: '/api' }))
      window.location.reload()
    }
  }

  return (
    <div className="bg-amber-500/15 border-b border-amber-500/30 px-4 py-2.5 text-xs text-amber-200 flex flex-wrap items-center justify-between gap-3 sticky top-0 z-40 backdrop-blur-md">
      <div className="flex items-center gap-2 min-w-0">
        <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
        <span className="truncate">
          {customUrl ? (
            <span>
              <strong>External URL Configured:</strong> Your browser is trying to connect to <code className="text-amber-300 bg-amber-950/60 px-1 py-0.5 rounded">{customUrl}</code>. Since Vercel Serverless Function is active, you don't need Railway!
            </span>
          ) : (
            <span>
              <strong>Serverless API Connecting:</strong> {backendError || 'Cannot reach API at /api. Serverless function may be starting.'}
            </span>
          )}
        </span>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {customUrl && (
          <button
            onClick={handleUseServerless}
            className="px-3 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold flex items-center gap-1 shadow-sm transition-colors text-xs"
          >
            ⚡ Use Built-in Serverless (/api)
          </button>
        )}
        <button
          onClick={() => checkBackendHealth()}
          className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 flex items-center gap-1 border border-slate-700 transition-colors"
        >
          <RefreshCw className="w-3 h-3" /> Retry
        </button>
        <button
          onClick={() => setShowBackendModal(true)}
          className="px-2.5 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 font-medium flex items-center gap-1 border border-amber-500/40 transition-colors"
        >
          <Settings className="w-3 h-3" /> Settings
        </button>
      </div>
    </div>
  )
}

function MainLayout() {
  const { showBackendModal, setShowBackendModal } = useApp()

  return (
    <>
      <GlobalBackendBanner />
      <Routes>
        <Route path="/"       element={<Home />} />
        <Route path="/report" element={<FullReport />} />
      </Routes>
      <BackendConfigModal isOpen={showBackendModal} onClose={() => setShowBackendModal(false)} />
    </>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppProvider>
        <MainLayout />
      </AppProvider>
    </AuthProvider>
  )
}
