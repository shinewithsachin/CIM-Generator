import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, X, FileText, FileSpreadsheet, Image, Globe, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'
import { uploadDocuments, processDocuments, getProcessStatus } from '../services/api'
import toast from 'react-hot-toast'

const FILE_ICONS = {
  'application/pdf': FileText,
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': FileText,
  'application/msword': FileText,
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': FileSpreadsheet,
  'application/vnd.ms-excel': FileSpreadsheet,
  'text/csv': FileSpreadsheet,
  'image/png': Image,
  'image/jpeg': Image,
  'image/tiff': Image,
}

const FILE_COLORS = {
  pdf: 'text-red-500',
  docx: 'text-blue-500',
  xlsx: 'text-green-600',
  csv: 'text-emerald-500',
  image: 'text-purple-500',
  other: 'text-slate-500',
}

function getFileTypeColor(name) {
  const ext = name.split('.').pop().toLowerCase()
  if (['pdf'].includes(ext)) return FILE_COLORS.pdf
  if (['docx', 'doc', 'txt'].includes(ext)) return FILE_COLORS.docx
  if (['xlsx', 'xls'].includes(ext)) return FILE_COLORS.xlsx
  if (['csv'].includes(ext)) return FILE_COLORS.csv
  if (['png', 'jpg', 'jpeg', 'tiff', 'bmp'].includes(ext)) return FILE_COLORS.image
  return FILE_COLORS.other
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

export default function FileUpload({ sessionId, onProcessingComplete }) {
  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [processLog, setProcessLog] = useState([])
  const [status, setStatus] = useState('idle') // idle | uploaded | processing | ready | error

  const onDrop = useCallback((accepted) => {
    setFiles(prev => {
      const existingNames = new Set(prev.map(f => f.name))
      const newFiles = accepted.filter(f => !existingNames.has(f.name))
      return [...prev, ...newFiles]
    })
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    multiple: true,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
      'text/csv': ['.csv'],
      'text/plain': ['.txt'],
      'application/xml': ['.xml'],
      'text/xml': ['.xml'],
      'application/json': ['.json'],
      'image/*': ['.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif'],
      'text/html': ['.html', '.htm'],
    },
  })

  const removeFile = (name) => setFiles(prev => prev.filter(f => f.name !== name))

  const handleUploadAndProcess = async () => {
    if (!files.length) return toast.error('Add at least one file')
    if (!sessionId) return toast.error('No session. Please restart.')

    setUploading(true)
    try {
      await uploadDocuments(sessionId, files)
      setStatus('uploaded')
      toast.success(`${files.length} file(s) uploaded`)
    } catch (e) {
      toast.error('Upload failed: ' + (e?.response?.data?.detail || e.message))
      setUploading(false)
      return
    }
    setUploading(false)

    // Start processing
    setProcessing(true)
    setStatus('processing')
    setProcessLog(['Starting document processing...'])

    try {
      await processDocuments(sessionId)
    } catch (e) {
      toast.error('Processing start failed: ' + (e?.response?.data?.detail || e.message))
      setProcessing(false)
      setStatus('error')
      return
    }

    // Poll for status
    const poll = setInterval(async () => {
      try {
        const s = await getProcessStatus(sessionId)
        setProcessLog(s.log || [])
        if (s.status === 'ready') {
          clearInterval(poll)
          setProcessing(false)
          setStatus('ready')
          toast.success('Documents indexed! Ready to generate CIM.')
          onProcessingComplete?.()
        } else if (s.status === 'error') {
          clearInterval(poll)
          setProcessing(false)
          setStatus('error')
          toast.error('Processing failed. Check logs below.')
        }
      } catch {
        clearInterval(poll)
        setProcessing(false)
        setStatus('error')
      }
    }, 2000)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-10 h-10 rounded-xl bg-indigo-100 flex items-center justify-center">
          <Upload className="text-indigo-700" size={20} />
        </div>
        <div>
          <h2 className="text-lg font-bold text-slate-900">Upload Company Documents</h2>
          <p className="text-sm text-slate-500">Supports 40+ documents in any format</p>
        </div>
      </div>

      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all duration-150
          ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-slate-300 bg-slate-50 hover:border-blue-400 hover:bg-blue-50/30'}`}
      >
        <input {...getInputProps()} />
        <Upload className="mx-auto text-slate-400 mb-3" size={36} />
        <p className="text-slate-700 font-semibold text-base">
          {isDragActive ? 'Drop files here...' : 'Drag & drop files, or click to browse'}
        </p>
        <p className="text-slate-400 text-sm mt-1">
          PDF, DOCX, XLSX, CSV, XML, JSON, TXT, PNG/JPG, HTML — no limit on file count
        </p>
      </div>

      {/* Supported formats */}
      <div className="flex flex-wrap gap-2">
        {['PDF', 'DOCX', 'XLSX', 'CSV', 'XML', 'JSON', 'TXT', 'Images', 'HTML'].map(fmt => (
          <span key={fmt} className="px-2.5 py-1 bg-slate-100 text-slate-600 rounded-md text-xs font-medium">{fmt}</span>
        ))}
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-slate-700">{files.length} file(s) selected</p>
            <button
              onClick={() => setFiles([])}
              className="text-xs text-slate-400 hover:text-red-500 transition-colors"
            >
              Clear all
            </button>
          </div>
          <div className="max-h-64 overflow-y-auto space-y-1.5 pr-1">
            {files.map(f => (
              <div key={f.name} className="flex items-center gap-3 px-3 py-2.5 bg-slate-50 rounded-lg border border-slate-200">
                <FileText size={16} className={getFileTypeColor(f.name)} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-700 truncate">{f.name}</p>
                  <p className="text-xs text-slate-400">{formatBytes(f.size)}</p>
                </div>
                {status === 'idle' && (
                  <button onClick={() => removeFile(f.name)} className="text-slate-300 hover:text-red-400 transition-colors flex-shrink-0">
                    <X size={15} />
                  </button>
                )}
                {status === 'ready' && <CheckCircle size={15} className="text-emerald-500 flex-shrink-0" />}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Process log */}
      {processLog.length > 0 && (
        <div className="bg-slate-900 rounded-xl p-4 max-h-52 overflow-y-auto font-mono text-xs">
          {processLog.map((line, i) => (
            <div key={i} className={`leading-5 ${line.startsWith('✓') ? 'text-emerald-400' : line.startsWith('✗') ? 'text-red-400' : 'text-slate-300'}`}>
              {line}
            </div>
          ))}
          {processing && (
            <div className="text-amber-400 flex items-center gap-2 mt-1">
              <span className="animate-spin inline-block w-3 h-3 border-2 border-amber-400 border-t-transparent rounded-full" />
              Processing...
            </div>
          )}
        </div>
      )}

      {/* Status banner */}
      {status === 'ready' && (
        <div className="flex items-center gap-3 bg-emerald-50 border border-emerald-200 rounded-lg p-4">
          <CheckCircle className="text-emerald-600 flex-shrink-0" size={20} />
          <div>
            <p className="text-emerald-800 font-semibold text-sm">Documents processed successfully!</p>
            <p className="text-emerald-600 text-xs mt-0.5">All documents are indexed and ready for CIM generation.</p>
          </div>
        </div>
      )}

      {status === 'error' && (
        <div className="flex items-center gap-3 bg-red-50 border border-red-200 rounded-lg p-4">
          <AlertCircle className="text-red-600 flex-shrink-0" size={20} />
          <p className="text-red-700 text-sm font-medium">Processing encountered errors. Check the log above.</p>
        </div>
      )}

      {/* Action button */}
      {status !== 'ready' && (
        <button
          onClick={handleUploadAndProcess}
          disabled={uploading || processing || files.length === 0}
          className="w-full btn-primary justify-center py-3 text-base"
        >
          {uploading ? (
            <><Loader2 size={18} className="animate-spin" /> Uploading...</>
          ) : processing ? (
            <><Loader2 size={18} className="animate-spin" /> Processing Documents...</>
          ) : (
            <><Upload size={18} /> Upload & Index Documents</>
          )}
        </button>
      )}
    </div>
  )
}
