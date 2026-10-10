import React, { useState, useEffect } from 'react'
import { Server, CheckCircle2, AlertTriangle, X, RefreshCw, ExternalLink } from 'lucide-react'
import axios from 'axios'
import { getApiBase, setApiBase } from '../api/client'

export default function BackendConfigModal({ isOpen, onClose }) {
  const [url, setUrl] = useState('')
  const [isTesting, setIsTesting] = useState(false)
  const [testResult, setTestResult] = useState(null) // { success: bool, message: string }

  useEffect(() => {
    if (isOpen) {
      setUrl(getApiBase())
      setTestResult(null)
    }
  }, [isOpen])

  if (!isOpen) return null

  const handleTest = async (testUrl) => {
    setIsTesting(true)
    setTestResult(null)
    let clean = (testUrl || url || '').trim().replace(/\/+$/, '')
    if (!clean.endsWith('/api') && !clean.includes('/api/')) {
      clean = `${clean}/api`
    }

    try {
      const res = await axios.get(`${clean}/health`, { timeout: 6000 })
      if (res.data?.status === 'ok') {
        setTestResult({
          success: true,
          message: `Connected successfully! (API v${res.data.version || '2.0'})`,
          normalizedUrl: clean,
        })
      } else {
        setTestResult({
          success: false,
          message: 'Received response, but health probe did not return status: ok',
        })
      }
    } catch (err) {
      setTestResult({
        success: false,
        message: err.message || 'Failed to connect. Ensure CORS and URL are correct.',
      })
    } finally {
      setIsTesting(false)
    }
  }

  const handleSave = () => {
    let clean = url.trim()
    if (clean === '/api' || clean === '') {
      setApiBase('')
    } else {
      setApiBase(clean)
    }
    onClose()
    window.location.reload()
  }

  const handleReset = () => {
    setApiBase('')
    setUrl('/api')
    setTestResult(null)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
            <Server className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Backend API Connection</h2>
            <p className="text-xs text-slate-400">Connect this frontend to your deployed Railway backend</p>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Backend API Base URL
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={url}
                onChange={(e) => {
                  setUrl(e.target.value)
                  setTestResult(null)
                }}
                placeholder="https://gst-intelligence-production-xxxx.up.railway.app/api"
                className="flex-1 input-field py-2 px-3 text-sm"
              />
              <button
                onClick={() => handleTest(url)}
                disabled={isTesting || !url}
                className="px-3 py-2 rounded-xl bg-slate-800 border border-slate-700 hover:border-slate-600 text-xs text-slate-300 font-medium flex items-center gap-1.5 transition-colors disabled:opacity-50"
              >
                {isTesting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                Test
              </button>
            </div>
            <p className="text-[11px] text-slate-500 mt-1.5">
              Paste your public Railway URL ending with <code className="text-blue-400">/api</code>.
            </p>
          </div>

          {testResult && (
            <div
              className={`p-3 rounded-xl border text-xs flex items-start gap-2.5 ${
                testResult.success
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                  : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
              }`}
            >
              {testResult.success ? (
                <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400 mt-0.5" />
              ) : (
                <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
              )}
              <div className="flex-1">
                <p className="font-semibold">{testResult.success ? 'Connection Successful' : 'Connection Failed'}</p>
                <p className="opacity-90 mt-0.5">{testResult.message}</p>
              </div>
            </div>
          )}

          <div className="bg-slate-800/40 border border-slate-800 rounded-xl p-3 text-xs text-slate-400 space-y-1.5">
            <p className="font-semibold text-slate-300">💡 Permanent Vercel Configuration:</p>
            <p>
              In your Vercel Project Dashboard, navigate to <strong>Settings</strong> → <strong>Environment Variables</strong> and add:
            </p>
            <div className="bg-slate-900 px-2.5 py-1.5 rounded-lg font-mono text-[11px] text-blue-300 border border-slate-800">
              VITE_API_URL = https://your-railway-url.up.railway.app/api
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 mt-6 pt-4 border-t border-slate-800">
          <button
            onClick={handleReset}
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
          >
            Reset to default (/api)
          </button>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs text-slate-400 hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="btn-primary text-xs px-4 py-2 rounded-xl"
            >
              Save & Connect
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
