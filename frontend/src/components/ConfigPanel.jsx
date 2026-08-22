import { useState } from 'react'
import { Settings, Eye, EyeOff, CheckCircle, AlertCircle, Info } from 'lucide-react'
import { updateConfig } from '../services/api'
import toast from 'react-hot-toast'

const PROVIDERS = [
  {
    value: 'openai',
    label: 'OpenAI',
    placeholder: 'sk-...',
    hint: 'platform.openai.com/api-keys',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-4'],
  },
  {
    value: 'anthropic',
    label: 'Anthropic',
    placeholder: 'sk-ant-...',
    hint: 'console.anthropic.com/settings/keys',
    models: ['claude-opus-4-7', 'claude-sonnet-4-6', 'claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022'],
  },
  {
    value: 'gemini',
    label: 'Gemini',
    placeholder: 'AIza...',
    hint: 'aistudio.google.com/app/apikey',
    models: ['gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-1.5-flash'],
  },
  {
    value: 'grok',
    label: 'Grok (xAI)',
    placeholder: 'xai-...',
    hint: 'console.x.ai',
    models: ['grok-3', 'grok-3-mini', 'grok-2'],
  },
  {
    value: 'groq',
    label: 'Groq',
    placeholder: 'gsk_...',
    hint: 'console.groq.com/keys',
    models: ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768'],
  },
]

const EMBEDDING_MODELS = [
  { value: 'BAAI/bge-m3',           label: 'BGE-M3 (Best — 8192 tokens, 1024-dim)' },
  { value: 'BAAI/bge-large-en-v1.5',label: 'BGE-Large (High quality, 1024-dim)' },
  { value: 'all-mpnet-base-v2',     label: 'all-mpnet-base-v2 (Accurate, 768-dim)' },
  { value: 'all-MiniLM-L6-v2',     label: 'all-MiniLM-L6-v2 (Fast, 384-dim)' },
]

export default function ConfigPanel({ onSaved }) {
  const [provider, setProvider]         = useState('openai')
  const [apiKey, setApiKey]             = useState('')
  const [model, setModel]               = useState('gpt-4o')
  const [embeddingModel, setEmbedding]  = useState('BAAI/bge-m3')
  const [showKey, setShowKey]           = useState(false)
  const [saving, setSaving]             = useState(false)
  const [saved, setSaved]               = useState(false)

  const currentProvider = PROVIDERS.find(p => p.value === provider) || PROVIDERS[0]

  const handleProviderChange = (val) => {
    setProvider(val)
    const p = PROVIDERS.find(x => x.value === val)
    if (p) setModel(p.models[0])
    setSaved(false)
  }

  const handleSave = async () => {
    if (!apiKey.trim()) {
      toast.error('Please enter your API key')
      return
    }
    setSaving(true)
    try {
      await updateConfig({ llm_provider: provider, llm_api_key: apiKey, llm_model: model, embedding_model: embeddingModel })
      setSaved(true)
      toast.success('Configuration saved!')
      onSaved?.()
    } catch (e) {
      toast.error('Failed to save config: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center">
          <Settings className="text-blue-700" size={20} />
        </div>
        <div>
          <h2 className="text-lg font-bold text-slate-900">AI Configuration</h2>
          <p className="text-sm text-slate-500">Set your LLM provider and API key</p>
        </div>
      </div>

      {/* Info box */}
      <div className="flex gap-3 bg-blue-50 border border-blue-200 rounded-lg p-4">
        <Info size={18} className="text-blue-600 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-blue-800">
          <p className="font-semibold mb-1">How it works</p>
          <ul className="space-y-1 list-disc list-inside text-blue-700">
            <li>Embeddings run <strong>locally</strong> — no API key needed for document indexing</li>
            <li>LLM API key is used only for CIM content generation and chat</li>
            <li>Your key is stored in-memory only and never persisted to disk</li>
          </ul>
        </div>
      </div>

      {/* Provider */}
      <div>
        <label className="block text-sm font-semibold text-slate-700 mb-2">LLM Provider</label>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {PROVIDERS.map(p => (
            <button
              key={p.value}
              onClick={() => handleProviderChange(p.value)}
              className={`flex items-center justify-center gap-2 px-4 py-3 rounded-lg border-2 font-semibold text-sm transition-all
                ${provider === p.value
                  ? 'border-blue-600 bg-blue-50 text-blue-700'
                  : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'}`}
            >
              {p.label}
              {provider === p.value && <CheckCircle size={14} />}
            </button>
          ))}
        </div>
      </div>

      {/* API Key */}
      <div>
        <label className="block text-sm font-semibold text-slate-700 mb-2">
          {currentProvider.label} API Key
        </label>
        <div className="relative">
          <input
            type={showKey ? 'text' : 'password'}
            value={apiKey}
            onChange={e => { setApiKey(e.target.value); setSaved(false) }}
            placeholder={currentProvider.placeholder}
            className="input-field pr-12"
          />
          <button
            onClick={() => setShowKey(v => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
          >
            {showKey ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        </div>
        <p className="text-xs text-slate-400 mt-1">
          Get your key at {currentProvider.hint}
        </p>
      </div>

      {/* Model */}
      <div>
        <label className="block text-sm font-semibold text-slate-700 mb-2">Model</label>
        <select
          value={model}
          onChange={e => { setModel(e.target.value); setSaved(false) }}
          className="select-field"
        >
          {currentProvider.models.map(m => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
        <p className="text-xs text-slate-400 mt-1">
          GPT-4o or Claude Opus recommended for best CIM quality
        </p>
      </div>

      {/* Custom model override */}
      <div>
        <label className="block text-sm font-semibold text-slate-700 mb-2">
          Custom Model Name <span className="font-normal text-slate-400">(optional override)</span>
        </label>
        <input
          type="text"
          value={model}
          onChange={e => { setModel(e.target.value); setSaved(false) }}
          placeholder="e.g. gpt-4o, claude-opus-4-7"
          className="input-field"
        />
      </div>

      {/* Embedding model */}
      <div>
        <label className="block text-sm font-semibold text-slate-700 mb-2">
          Embedding Model <span className="font-normal text-slate-400">(runs locally)</span>
        </label>
        <select
          value={embeddingModel}
          onChange={e => { setEmbedding(e.target.value); setSaved(false) }}
          className="select-field"
        >
          {EMBEDDING_MODELS.map(m => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>
      </div>

      {/* Save button */}
      <button
        onClick={handleSave}
        disabled={saving || !apiKey.trim()}
        className={`w-full btn-primary justify-center py-3 ${saved ? 'bg-emerald-600 hover:bg-emerald-700' : ''}`}
      >
        {saving ? (
          <span className="animate-spin inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
        ) : saved ? (
          <><CheckCircle size={16} /> Configuration Saved</>
        ) : (
          <><Settings size={16} /> Save Configuration</>
        )}
      </button>
    </div>
  )
}
