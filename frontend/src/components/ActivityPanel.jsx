import { useEffect, useState } from 'react'
import { ShieldCheck, Loader2 } from 'lucide-react'
import { getMyAuditLog } from '../services/api'

const ACTION_LABELS = {
  register: 'Account registered',
  login: 'Signed in',
  session_create: 'Created a session',
  session_delete: 'Deleted a session',
  document_upload: 'Uploaded documents',
  config_update: 'Updated AI configuration',
  pdf_download: 'Downloaded CIM PDF',
}

export default function ActivityPanel() {
  const [events, setEvents] = useState(null)

  useEffect(() => {
    getMyAuditLog()
      .then(d => setEvents(d.events || []))
      .catch(() => setEvents([]))
  }, [])

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-200 flex-shrink-0">
        <div className="w-8 h-8 rounded-lg bg-slate-700 flex items-center justify-center">
          <ShieldCheck size={16} className="text-white" />
        </div>
        <div>
          <p className="text-sm font-bold text-slate-900">Activity Log</p>
          <p className="text-xs text-slate-400">Your account's audit trail</p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-2">
        {events === null && (
          <div className="flex items-center justify-center h-32">
            <Loader2 size={24} className="animate-spin text-slate-400" />
          </div>
        )}
        {events?.length === 0 && (
          <p className="text-sm text-slate-400 text-center py-8">No activity recorded yet.</p>
        )}
        {events?.map((e, i) => (
          <div key={i} className="flex items-start justify-between gap-3 px-3 py-2.5 bg-slate-50 rounded-lg border border-slate-200">
            <div>
              <p className="text-sm font-medium text-slate-700">{ACTION_LABELS[e.action] || e.action}</p>
              {e.ip_address && <p className="text-xs text-slate-400">{e.ip_address}</p>}
            </div>
            <p className="text-xs text-slate-400 whitespace-nowrap">{e.created_at}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
