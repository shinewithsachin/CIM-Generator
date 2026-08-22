import { useState } from 'react'
import { BookOpen, Eye, EyeOff, Loader2, CheckCircle, AlertCircle, LogIn, UserPlus } from 'lucide-react'
import { registerUser, loginUser } from '../services/api'
import toast from 'react-hot-toast'

export default function AuthPage({ onAuth }) {
  const [mode, setMode]         = useState('login')   // login | register
  const [email, setEmail]       = useState('')
  const [name, setName]         = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm]   = useState('')
  const [showPw, setShowPw]     = useState(false)
  const [loading, setLoading]   = useState(false)
  const [errors, setErrors]     = useState({})

  const validate = () => {
    const e = {}
    if (!email.trim())             e.email    = 'Email is required'
    else if (!/\S+@\S+\.\S+/.test(email)) e.email = 'Enter a valid email'
    if (!password)                 e.password = 'Password is required'
    if (mode === 'register') {
      if (!name.trim())            e.name     = 'Name is required'
      if (password.length < 8)    e.password = 'Password must be at least 8 characters'
      if (password !== confirm)   e.confirm  = 'Passwords do not match'
    }
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setLoading(true)
    try {
      let result
      if (mode === 'register') {
        result = await registerUser(email, name, password)
        toast.success('Account created! Welcome.')
      } else {
        result = await loginUser(email, password)
        toast.success(`Welcome back, ${result.user.name}!`)
      }
      onAuth(result.token, result.user)
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Something went wrong. Please try again.'
      toast.error(msg)
      setErrors({ general: msg })
    } finally {
      setLoading(false)
    }
  }

  const switchMode = (m) => {
    setMode(m)
    setErrors({})
    setPassword('')
    setConfirm('')
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-[#0F2B5B] to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">

        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-amber-500 mb-4 shadow-lg shadow-amber-500/30">
            <BookOpen size={32} className="text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white">CIM Generator</h1>
          <p className="text-blue-300 mt-1 text-sm">AI-Powered Investment Memorandum</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-2xl overflow-hidden">

          {/* Tab switcher */}
          <div className="grid grid-cols-2 border-b border-slate-200">
            <button
              onClick={() => switchMode('login')}
              className={`py-4 text-sm font-semibold transition-all
                ${mode === 'login' ? 'text-blue-700 bg-blue-50 border-b-2 border-blue-600' : 'text-slate-500 hover:text-slate-700'}`}
            >
              <span className="flex items-center justify-center gap-2">
                <LogIn size={16} /> Sign In
              </span>
            </button>
            <button
              onClick={() => switchMode('register')}
              className={`py-4 text-sm font-semibold transition-all
                ${mode === 'register' ? 'text-blue-700 bg-blue-50 border-b-2 border-blue-600' : 'text-slate-500 hover:text-slate-700'}`}
            >
              <span className="flex items-center justify-center gap-2">
                <UserPlus size={16} /> Create Account
              </span>
            </button>
          </div>

          <form onSubmit={handleSubmit} className="p-8 space-y-5">
            <div>
              <h2 className="text-xl font-bold text-slate-900">
                {mode === 'login' ? 'Welcome back' : 'Create your account'}
              </h2>
              <p className="text-slate-500 text-sm mt-1">
                {mode === 'login'
                  ? 'Your documents are private and visible only to you.'
                  : 'Your account keeps all your CIM projects private and secure.'}
              </p>
            </div>

            {/* Name (register only) */}
            {mode === 'register' && (
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1.5">Full Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={e => { setName(e.target.value); setErrors(p => ({...p, name: ''})) }}
                  placeholder="Your full name"
                  className={`input-field ${errors.name ? 'border-red-400 focus:ring-red-400' : ''}`}
                  autoComplete="name"
                />
                {errors.name && <p className="text-red-500 text-xs mt-1">{errors.name}</p>}
              </div>
            )}

            {/* Email */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1.5">Email Address</label>
              <input
                type="email"
                value={email}
                onChange={e => { setEmail(e.target.value); setErrors(p => ({...p, email: ''})) }}
                placeholder="you@company.com"
                className={`input-field ${errors.email ? 'border-red-400 focus:ring-red-400' : ''}`}
                autoComplete="email"
              />
              {errors.email && <p className="text-red-500 text-xs mt-1">{errors.email}</p>}
            </div>

            {/* Password */}
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1.5">Password</label>
              <div className="relative">
                <input
                  type={showPw ? 'text' : 'password'}
                  value={password}
                  onChange={e => { setPassword(e.target.value); setErrors(p => ({...p, password: ''})) }}
                  placeholder={mode === 'register' ? 'At least 8 characters' : 'Your password'}
                  className={`input-field pr-11 ${errors.password ? 'border-red-400 focus:ring-red-400' : ''}`}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                />
                <button
                  type="button"
                  onClick={() => setShowPw(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
              {errors.password && <p className="text-red-500 text-xs mt-1">{errors.password}</p>}
            </div>

            {/* Confirm password (register only) */}
            {mode === 'register' && (
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1.5">Confirm Password</label>
                <input
                  type={showPw ? 'text' : 'password'}
                  value={confirm}
                  onChange={e => { setConfirm(e.target.value); setErrors(p => ({...p, confirm: ''})) }}
                  placeholder="Repeat your password"
                  className={`input-field ${errors.confirm ? 'border-red-400 focus:ring-red-400' : ''}`}
                  autoComplete="new-password"
                />
                {errors.confirm && <p className="text-red-500 text-xs mt-1">{errors.confirm}</p>}
              </div>
            )}

            {/* General error */}
            {errors.general && (
              <div className="flex items-center gap-2 text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm">
                <AlertCircle size={16} className="flex-shrink-0" />
                {errors.general}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary justify-center py-3 text-base mt-2"
            >
              {loading
                ? <><Loader2 size={18} className="animate-spin" /> {mode === 'login' ? 'Signing in...' : 'Creating account...'}</>
                : mode === 'login'
                  ? <><LogIn size={18} /> Sign In</>
                  : <><UserPlus size={18} /> Create Account</>}
            </button>

            {/* Privacy note */}
            <div className="flex items-start gap-2 bg-blue-50 border border-blue-100 rounded-lg px-4 py-3">
              <CheckCircle size={15} className="text-blue-500 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-blue-700 leading-relaxed">
                <strong>Your documents are private.</strong> Every file you upload is stored in a
                session linked exclusively to your account. Other users cannot access your data.
              </p>
            </div>
          </form>
        </div>

        <p className="text-center text-blue-300/60 text-xs mt-6">
          CIM Generator — Confidential Investment Memorandum System
        </p>
      </div>
    </div>
  )
}
