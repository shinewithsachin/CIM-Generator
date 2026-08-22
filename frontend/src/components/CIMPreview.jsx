import { useState, useEffect, useRef } from 'react'
import {
  FileText, RefreshCw, Download, CheckCircle, Loader2,
  AlertCircle, ChevronDown, ChevronUp, Zap, Play, KeyRound, Copy
} from 'lucide-react'
import {
  getAllSections, generateAllSections, getGenerationStatus,
  generatePDF, getPDFStatus, downloadPDFUrl
} from '../services/api'
import SectionEditor from './SectionEditor'
import toast from 'react-hot-toast'

const CIM_SECTIONS = [
  'executive_summary', 'investment_thesis', 'market_overview', 'company_overview',
  'products_services', 'revenue_profile', 'employee_profile', 'customer_profile',
  'financials', 'management_structure',
]

const SECTION_NAMES = {
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

export default function CIMPreview({ sessionId }) {
  const [sections, setSections]         = useState({})
  const [generating, setGenerating]     = useState(false)
  const [genProgress, setGenProgress]   = useState({ done: [], total: [] })
  const [pdfStatus, setPdfStatus]       = useState('not_started')
  const [pdfGenerating, setPdfGen]      = useState(false)
  const [expandedSection, setExpanded]  = useState(null)
  const [loading, setLoading]           = useState(true)
  const [pdfPassword, setPdfPassword]   = useState(null)
  const genPollRef = useRef(null)
  const pdfPollRef = useRef(null)

  // Load existing sections on mount
  useEffect(() => {
    if (!sessionId) return
    getAllSections(sessionId)
      .then(d => { setSections(d.sections || {}); setLoading(false) })
      .catch(() => setLoading(false))
  }, [sessionId])

  useEffect(() => () => {
    clearInterval(genPollRef.current)
    clearInterval(pdfPollRef.current)
  }, [])

  const handleGenerateAll = async () => {
    setGenerating(true)
    setGenProgress({ done: [], total: CIM_SECTIONS })
    try {
      await generateAllSections(sessionId, null)
    } catch (e) {
      toast.error('Generation failed: ' + (e?.response?.data?.detail || e.message))
      setGenerating(false)
      return
    }

    // Poll
    genPollRef.current = setInterval(async () => {
      try {
        const s = await getGenerationStatus(sessionId)
        setGenProgress({ done: s.done || [], total: s.total || CIM_SECTIONS })

        // Update sections as they complete
        if (s.sections_ready?.length) {
          const fresh = await getAllSections(sessionId)
          setSections(fresh.sections || {})
        }

        if (s.status === 'generated' || s.done?.length >= CIM_SECTIONS.length) {
          clearInterval(genPollRef.current)
          setGenerating(false)
          const fresh = await getAllSections(sessionId)
          setSections(fresh.sections || {})
          toast.success('All sections generated!')
          if (s.done?.length > 0) setExpanded(CIM_SECTIONS[0])
        } else if (s.status === 'error') {
          clearInterval(genPollRef.current)
          setGenerating(false)
          toast.error('Generation encountered errors')
        }
      } catch {
        clearInterval(genPollRef.current)
        setGenerating(false)
      }
    }, 3000)
  }

  const handleGeneratePDF = async () => {
    setPdfGen(true)
    setPdfStatus('generating')
    try {
      await generatePDF(sessionId)
    } catch (e) {
      toast.error('PDF generation failed: ' + (e?.response?.data?.detail || e.message))
      setPdfGen(false)
      setPdfStatus('error')
      return
    }

    pdfPollRef.current = setInterval(async () => {
      try {
        const s = await getPDFStatus(sessionId)
        if (s.status === 'ready') {
          clearInterval(pdfPollRef.current)
          setPdfGen(false)
          setPdfStatus('ready')
          setPdfPassword(s.pdf_password || null)
          toast.success('PDF ready for download!')
        } else if (s.status === 'error') {
          clearInterval(pdfPollRef.current)
          setPdfGen(false)
          setPdfStatus('error')
          toast.error('PDF generation failed')
        }
      } catch {
        clearInterval(pdfPollRef.current)
        setPdfGen(false)
      }
    }, 2000)
  }

  const handleSectionUpdate = (key, data) => {
    setSections(prev => ({ ...prev, [key]: data }))
  }

  const completedSections = Object.keys(sections).filter(k => sections[k]?.content)
  const progress = CIM_SECTIONS.length > 0 ? (completedSections.length / CIM_SECTIONS.length) * 100 : 0

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={32} className="animate-spin text-blue-500" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header & actions */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">CIM Sections</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            {completedSections.length} / {CIM_SECTIONS.length} sections generated
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={handleGenerateAll}
            disabled={generating}
            className="btn-primary"
          >
            {generating
              ? <><Loader2 size={16} className="animate-spin" /> Generating All...</>
              : <><Zap size={16} /> Generate All Sections</>}
          </button>
          {completedSections.length > 0 && (
            <button
              onClick={handleGeneratePDF}
              disabled={pdfGenerating}
              className="btn-success"
            >
              {pdfGenerating
                ? <><Loader2 size={16} className="animate-spin" /> Building PDF...</>
                : <><FileText size={16} /> Generate PDF</>}
            </button>
          )}
          {pdfStatus === 'ready' && (
            <a
              href={downloadPDFUrl(sessionId)}
              download
              className="btn-primary bg-emerald-600 hover:bg-emerald-700 no-underline"
            >
              <Download size={16} /> Download PDF
            </a>
          )}
        </div>
      </div>

      {/* Progress bar */}
      {(generating || completedSections.length > 0) && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>Progress</span>
            <span>{Math.round(progress)}%</span>
          </div>
          <div className="w-full h-2 bg-slate-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-600 rounded-full transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
          {generating && (
            <div className="flex flex-wrap gap-2">
              {CIM_SECTIONS.map(s => {
                const done = genProgress.done.includes(s)
                const current = generating && genProgress.done.length === CIM_SECTIONS.indexOf(s)
                return (
                  <span key={s} className={`section-badge
                    ${done ? 'bg-emerald-100 text-emerald-700' : current ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-500'}`}>
                    {done ? '✓' : current ? '⟳' : '○'} {SECTION_NAMES[s]?.split('. ')[1] || s}
                  </span>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* PDF status */}
      {pdfStatus === 'generating' && (
        <div className="flex items-center gap-3 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <Loader2 className="text-blue-600 animate-spin flex-shrink-0" size={20} />
          <p className="text-blue-800 text-sm font-medium">Generating professional PDF with charts and formatting...</p>
        </div>
      )}
      {pdfStatus === 'ready' && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-3">
              <CheckCircle className="text-emerald-600 flex-shrink-0" size={20} />
              <p className="text-emerald-800 text-sm font-semibold">PDF generated successfully!</p>
            </div>
            <a
              href={downloadPDFUrl(sessionId)}
              download
              className="btn-success text-sm py-2"
            >
              <Download size={15} /> Download CIM PDF
            </a>
          </div>
          {pdfPassword && (
            <div className="flex items-center gap-2 bg-white border border-emerald-200 rounded-lg px-3 py-2">
              <KeyRound size={14} className="text-emerald-600 flex-shrink-0" />
              <p className="text-xs text-slate-600">
                This CIM is password-protected — it's a confidential memo. Open password:{' '}
                <code className="font-mono font-semibold text-slate-900">{pdfPassword}</code>
              </p>
              <button
                onClick={() => { navigator.clipboard?.writeText(pdfPassword); toast.success('Password copied') }}
                className="ml-auto text-slate-400 hover:text-emerald-600 flex-shrink-0"
                title="Copy password"
              >
                <Copy size={14} />
              </button>
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {completedSections.length === 0 && !generating && (
        <div className="card p-12 text-center">
          <FileText size={48} className="mx-auto text-slate-300 mb-4" />
          <h3 className="text-lg font-semibold text-slate-600 mb-2">No sections generated yet</h3>
          <p className="text-slate-400 text-sm mb-6">
            Click "Generate All Sections" to create a complete CIM from your uploaded documents.
            <br />Each section takes ~30–60 seconds.
          </p>
          <button onClick={handleGenerateAll} disabled={generating} className="btn-primary mx-auto">
            <Zap size={16} /> Generate All Sections
          </button>
        </div>
      )}

      {/* Section list */}
      <div className="space-y-3">
        {CIM_SECTIONS.map(key => {
          const sec = sections[key]
          const isExpanded = expandedSection === key
          const isDone = !!sec?.content
          const isCurrentlyGenerating = generating && genProgress.done.length === CIM_SECTIONS.indexOf(key)

          return (
            <div key={key} className={`card overflow-hidden transition-all duration-150
              ${isDone ? 'border-slate-200' : 'border-dashed border-slate-300'}`}>
              {/* Section header */}
              <button
                onClick={() => setExpanded(isExpanded ? null : key)}
                className="w-full flex items-center justify-between px-5 py-4 hover:bg-slate-50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0
                    ${isDone ? 'bg-emerald-100 text-emerald-700' : isCurrentlyGenerating ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-400'}`}>
                    {isDone ? '✓' : isCurrentlyGenerating ? '⟳' : (CIM_SECTIONS.indexOf(key) + 1)}
                  </div>
                  <span className="font-semibold text-slate-800 text-sm">
                    {SECTION_NAMES[key]}
                  </span>
                  {isCurrentlyGenerating && (
                    <Loader2 size={14} className="animate-spin text-blue-500" />
                  )}
                  {sec?.manually_edited && (
                    <span className="section-badge bg-amber-100 text-amber-600 text-xs">Edited</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {isDone && (
                    <span className="text-xs text-slate-400">
                      {sec.content?.length?.toLocaleString()} chars
                    </span>
                  )}
                  {isExpanded ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
                </div>
              </button>

              {/* Expanded content */}
              {isExpanded && isDone && (
                <div className="border-t border-slate-100">
                  <SectionEditor
                    sessionId={sessionId}
                    sectionKey={key}
                    sectionData={sec}
                    onUpdate={handleSectionUpdate}
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
