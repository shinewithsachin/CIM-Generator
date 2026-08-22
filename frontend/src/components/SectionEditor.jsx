import { useState } from 'react'
import { Edit3, Save, RefreshCw, X, CheckCircle, Loader2, Eye, Code } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { updateSection, generateSection } from '../services/api'
import toast from 'react-hot-toast'

const SECTION_DISPLAY_NAMES = {
  executive_summary:    '1. Executive Summary',
  investment_thesis:    '2. Investment Thesis',
  market_overview:      '3. Market Overview',
  company_overview:     '4. Company Overview',
  products_services:    '5. Products & Services',
  revenue_profile:      '6. Revenue Profile',
  employee_profile:     '7. Employee Profile',
  customer_profile:     '8. Customer Profile',
  financials:           '9. Financials',
  management_structure: '10. Management Structure',
}

export default function SectionEditor({ sessionId, sectionKey, sectionData, onUpdate }) {
  const [editing, setEditing]       = useState(false)
  const [editContent, setEditContent] = useState('')
  const [saving, setSaving]         = useState(false)
  const [regenerating, setRegen]    = useState(false)
  const [viewMode, setViewMode]     = useState('preview') // preview | raw

  const content = sectionData?.content || ''
  const charts  = sectionData?.charts  || []
  const label   = SECTION_DISPLAY_NAMES[sectionKey] || sectionKey

  const startEdit = () => {
    setEditContent(content)
    setEditing(true)
  }

  const cancelEdit = () => {
    setEditing(false)
    setEditContent('')
  }

  const saveEdit = async () => {
    setSaving(true)
    try {
      await updateSection(sessionId, sectionKey, editContent)
      onUpdate?.(sectionKey, { ...sectionData, content: editContent })
      setEditing(false)
      toast.success('Section saved')
    } catch (e) {
      toast.error('Save failed: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setSaving(false)
    }
  }

  const handleRegenerate = async () => {
    setRegen(true)
    try {
      const result = await generateSection(sessionId, sectionKey)
      onUpdate?.(sectionKey, result)
      toast.success(`${label} regenerated`)
    } catch (e) {
      toast.error('Regeneration failed: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setRegen(false)
    }
  }

  return (
    <div className="card overflow-hidden">
      {/* Section header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-slate-50">
        <h3 className="font-bold text-slate-900 text-base">{label}</h3>
        <div className="flex items-center gap-2">
          {sectionData?.manually_edited && (
            <span className="section-badge bg-amber-100 text-amber-700">
              <Edit3 size={11} /> Edited
            </span>
          )}
          {!editing && (
            <>
              <button
                onClick={() => setViewMode(v => v === 'preview' ? 'raw' : 'preview')}
                className="btn-secondary text-xs px-3 py-1.5"
                title="Toggle view"
              >
                {viewMode === 'preview' ? <Code size={14} /> : <Eye size={14} />}
              </button>
              <button
                onClick={handleRegenerate}
                disabled={regenerating}
                className="btn-secondary text-xs px-3 py-1.5"
                title="Regenerate with AI"
              >
                {regenerating
                  ? <Loader2 size={14} className="animate-spin" />
                  : <RefreshCw size={14} />}
                {regenerating ? 'Regenerating...' : 'Regenerate'}
              </button>
              <button onClick={startEdit} className="btn-primary text-xs px-3 py-1.5">
                <Edit3 size={14} /> Edit
              </button>
            </>
          )}
          {editing && (
            <>
              <button onClick={cancelEdit} className="btn-secondary text-xs px-3 py-1.5">
                <X size={14} /> Cancel
              </button>
              <button onClick={saveEdit} disabled={saving} className="btn-success text-xs px-3 py-1.5">
                {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                {saving ? 'Saving...' : 'Save'}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Content area */}
      <div className="p-5">
        {editing ? (
          <textarea
            value={editContent}
            onChange={e => setEditContent(e.target.value)}
            className="w-full h-[500px] input-field font-mono text-xs leading-5 resize-y"
            placeholder="Edit section content (Markdown supported)..."
          />
        ) : viewMode === 'preview' ? (
          <div className="prose-cim max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </div>
        ) : (
          <pre className="text-xs font-mono text-slate-600 whitespace-pre-wrap bg-slate-50 rounded-lg p-4 overflow-auto max-h-[600px]">
            {content}
          </pre>
        )}

        {/* Charts info */}
        {charts.length > 0 && !editing && (
          <div className="mt-4 pt-4 border-t border-slate-100">
            <p className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wide">
              {charts.length} Chart(s) will be embedded in PDF
            </p>
            <div className="flex flex-wrap gap-2">
              {charts.map((c, i) => (
                <span key={i} className="section-badge bg-blue-50 text-blue-700">
                  {c.type?.toUpperCase()}: {c.title}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
