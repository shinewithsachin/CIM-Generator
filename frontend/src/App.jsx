import { useState, useEffect } from 'react'
import { Toaster } from 'react-hot-toast'
import {
  Settings, Upload, MessageSquare, FileText,
  ChevronRight, CheckCircle, Loader2,
  BarChart3, Menu, X as XIcon, BookOpen, LogOut, User, ShieldCheck
} from 'lucide-react'
import ConfigPanel from './components/ConfigPanel'
import FileUpload from './components/FileUpload'
import ChatInterface from './components/ChatInterface'
import ActivityPanel from './components/ActivityPanel'
import CIMPreview from './components/CIMPreview'
import AuthPage from './components/AuthPage'
import { createSession, getSession } from './services/api'
import toast from 'react-hot-toast'

const STEPS = [
  { id: 'config',   label: 'Configure AI',     icon: Settings,  desc: 'Set API key & model' },
  { id: 'upload',   label: 'Upload Documents',  icon: Upload,    desc: 'Upload company files' },
  { id: 'generate', label: 'Generate & Review', icon: BarChart3, desc: 'Generate CIM sections' },
]

// ─── Auth state helpers ────────────────────────────────
function loadAuth() {
  try {
    const token = localStorage.getItem('cim_token')
    const user  = JSON.parse(localStorage.getItem('cim_user') || 'null')
    return token && user ? { token, user } : null
  } catch { return null }
}

function saveAuth(token, user) {
  localStorage.setItem('cim_token', token)
  localStorage.setItem('cim_user', JSON.stringify(user))
}

function clearAuth() {
  localStorage.removeItem('cim_token')
  localStorage.removeItem('cim_user')
  localStorage.removeItem('cim_session_id')
}


export default function App() {
  const [authState, setAuthState]     = useState(loadAuth)   // null | { token, user }
  const [step, setStep]               = useState('config')
  const [sessionId, setSessionId]     = useState(null)
  const [sessionStatus, setStatus]    = useState('created')
  const [configSaved, setConfigSaved] = useState(false)
  const [docsReady, setDocsReady]     = useState(false)
  const [chatOpen, setChatOpen]       = useState(false)
  const [activityOpen, setActivityOpen] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const drawerOpen = chatOpen || activityOpen

  // Listen for 401 events from the API interceptor
  useEffect(() => {
    const handle401 = () => {
      setAuthState(null)
      toast.error('Session expired. Please log in again.')
    }
    window.addEventListener('cim:unauthorized', handle401)
    return () => window.removeEventListener('cim:unauthorized', handle401)
  }, [])

  // Init session when user is authenticated
  useEffect(() => {
    if (!authState) return
    const storedId = localStorage.getItem('cim_session_id')
    if (storedId) {
      getSession(storedId)
        .then(s => {
          setSessionId(s.id)
          setStatus(s.status)
          if (s.status === 'ready' || s.status === 'generated') {
            setDocsReady(true)
            setConfigSaved(true)
            setStep('generate')
          }
        })
        .catch(() => {
          localStorage.removeItem('cim_session_id')
          initSession()
        })
    } else {
      initSession()
    }
  }, [authState])

  const initSession = async () => {
    try {
      const s = await createSession()
      setSessionId(s.session_id)
      localStorage.setItem('cim_session_id', s.session_id)
    } catch (e) {
      toast.error('Could not connect to backend. Is the server running?')
    }
  }

  const handleAuth = (token, user) => {
    saveAuth(token, user)
    setAuthState({ token, user })
  }

  const handleLogout = () => {
    clearAuth()
    setAuthState(null)
    setSessionId(null)
    setStatus('created')
    setConfigSaved(false)
    setDocsReady(false)
    setStep('config')
    toast.success('Logged out')
  }

  const newSession = async () => {
    if (!window.confirm('Start a new session? Your current documents and generated sections will stay saved under this session, but you will leave it and start fresh.')) {
      return
    }
    localStorage.removeItem('cim_session_id')
    setConfigSaved(false)
    setDocsReady(false)
    setStep('config')
    setStatus('created')
    await initSession()
  }

  const stepComplete = (id) => {
    if (id === 'config')   return configSaved
    if (id === 'upload')   return docsReady
    if (id === 'generate') return sessionStatus === 'generated'
    return false
  }

  const stepEnabled = (id) => {
    if (id === 'config')   return true
    if (id === 'upload')   return configSaved
    if (id === 'generate') return docsReady
    return false
  }

  // ── Show login/register if not authenticated ────────
  if (!authState) {
    return (
      <>
        <Toaster position="top-right" toastOptions={{ duration: 4000 }} />
        <AuthPage onAuth={handleAuth} />
      </>
    )
  }

  // ── Main app ────────────────────────────────────────
  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <Toaster position="top-right" toastOptions={{ duration: 4000 }} />

      {/* Top nav */}
      <header className="h-16 bg-[#0F2B5B] flex items-center justify-between px-6 shadow-lg z-30 flex-shrink-0">
        <div className="flex items-center gap-3">
          <button onClick={() => setSidebarOpen(v => !v)} className="text-white/70 hover:text-white lg:hidden">
            {sidebarOpen ? <XIcon size={20} /> : <Menu size={20} />}
          </button>
          <div className="w-8 h-8 rounded-lg bg-amber-500 flex items-center justify-center">
            <BookOpen size={18} className="text-white" />
          </div>
          <div>
            <h1 className="text-white font-bold text-base leading-tight">CIM Generator</h1>
            <p className="text-blue-300 text-xs">AI-Powered Investment Memorandum</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* User badge */}
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/10">
            <User size={14} className="text-blue-200" />
            <span className="text-white text-sm font-medium">{authState.user.name}</span>
          </div>

          {docsReady && (
            <button
              onClick={() => { setChatOpen(v => !v); setActivityOpen(false) }}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-semibold transition-all
                ${chatOpen ? 'bg-white text-[#0F2B5B]' : 'bg-white/10 text-white hover:bg-white/20'}`}
            >
              <MessageSquare size={15} /> Chat
            </button>
          )}

          <button
            onClick={() => { setActivityOpen(v => !v); setChatOpen(false) }}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-semibold transition-all
              ${activityOpen ? 'bg-white text-[#0F2B5B]' : 'bg-white/10 text-white hover:bg-white/20'}`}
            title="Your account's audit trail"
          >
            <ShieldCheck size={15} /> Activity
          </button>

          <button
            onClick={newSession}
            className="text-xs text-white/60 hover:text-white px-3 py-1.5 rounded-lg hover:bg-white/10 transition-all"
          >
            New Session
          </button>

          <button
            onClick={handleLogout}
            className="flex items-center gap-1.5 text-xs text-white/60 hover:text-white px-3 py-1.5 rounded-lg hover:bg-white/10 transition-all"
            title="Sign out"
          >
            <LogOut size={14} /> Logout
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className={`
          bg-white border-r border-slate-200 flex-shrink-0 flex flex-col
          transition-all duration-200 overflow-hidden
          ${sidebarOpen ? 'w-64' : 'w-0 lg:w-64'}
        `}>
          <div className="p-4 border-b border-slate-100">
            <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">Workflow</p>
          </div>

          <nav className="flex-1 overflow-y-auto p-3 space-y-1">
            {STEPS.map((s) => {
              const Icon = s.icon
              const isActive  = step === s.id
              const isDone    = stepComplete(s.id)
              const isEnabled = stepEnabled(s.id)

              return (
                <button
                  key={s.id}
                  onClick={() => isEnabled && setStep(s.id)}
                  disabled={!isEnabled}
                  className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl text-left transition-all
                    ${isActive   ? 'bg-blue-50 border-2 border-blue-200' : ''}
                    ${isEnabled && !isActive ? 'hover:bg-slate-50 border-2 border-transparent' : ''}
                    ${!isEnabled ? 'opacity-40 cursor-not-allowed border-2 border-transparent' : ''}`}
                >
                  <div className={`step-dot
                    ${isDone ? 'bg-emerald-500 text-white' : isActive ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-500'}`}>
                    {isDone ? <CheckCircle size={16} /> : <Icon size={16} />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-semibold truncate
                      ${isActive ? 'text-blue-700' : isDone ? 'text-emerald-700' : 'text-slate-600'}`}>
                      {s.label}
                    </p>
                    <p className="text-xs text-slate-400 truncate">{s.desc}</p>
                  </div>
                  {isActive && <ChevronRight size={14} className="text-blue-400 flex-shrink-0" />}
                </button>
              )
            })}
          </nav>

          {/* Privacy badge */}
          <div className="p-4 border-t border-slate-100">
            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-xs text-emerald-700">
              <p className="font-semibold flex items-center gap-1.5 mb-1">
                <CheckCircle size={12} /> Private & Secure
              </p>
              <p className="text-emerald-600 leading-relaxed">
                Your documents are linked to <strong>{authState.user.email}</strong> and
                are not accessible to other users.
              </p>
            </div>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto">
          <div className={`transition-all duration-200 ${drawerOpen ? 'lg:mr-96' : ''}`}>
            <div className="max-w-4xl mx-auto p-6 lg:p-8">
              {step === 'config' && (
                <div className="card p-6 md:p-8">
                  <ConfigPanel onSaved={() => { setConfigSaved(true); setStep('upload') }} />
                </div>
              )}
              {step === 'upload' && (
                <div className="card p-6 md:p-8">
                  <FileUpload
                    sessionId={sessionId}
                    onProcessingComplete={() => {
                      setDocsReady(true)
                      setStatus('ready')
                      setStep('generate')
                    }}
                  />
                </div>
              )}
              {step === 'generate' && sessionId && (
                <CIMPreview sessionId={sessionId} />
              )}
            </div>
          </div>
        </main>

        {/* Chat / Activity drawer — full-width overlay on mobile, side panel on lg+ */}
        {drawerOpen && (
          <aside className="w-full sm:w-96 flex-shrink-0 border-l border-slate-200 bg-white flex flex-col fixed right-0 top-16 bottom-0 z-20">
            {chatOpen && docsReady && sessionId && <ChatInterface sessionId={sessionId} />}
            {activityOpen && <ActivityPanel />}
          </aside>
        )}
      </div>
    </div>
  )
}
