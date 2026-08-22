import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, MessageSquare, RefreshCw, Loader2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { chat } from '../services/api'
import toast from 'react-hot-toast'

const SUGGESTED_QUESTIONS = [
  "What is the company's total revenue and EBITDA?",
  "Who are the top customers and what % of revenue do they represent?",
  "What are the key growth drivers for this company?",
  "Describe the competitive landscape and key competitors",
  "What are the main products/services and their revenue contribution?",
  "What is the management team's background and experience?",
  "What are the key financial projections for the next 3 years?",
  "What is the total addressable market size?",
]

export default function ChatInterface({ sessionId }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Hello! I'm your CIM research assistant. I have access to all your uploaded documents and can answer questions about the company, financials, market, competitors, and more. What would you like to know?",
    }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const endRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async (text) => {
    const msg = (text || input).trim()
    if (!msg || loading) return

    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: msg }])
    setLoading(true)

    try {
      const res = await chat(sessionId, msg)
      setMessages(prev => [...prev, { role: 'assistant', content: res.answer }])
    } catch (e) {
      const errMsg = e?.response?.data?.detail || 'Failed to get response. Check your API key configuration.'
      setMessages(prev => [...prev, { role: 'assistant', content: `**Error:** ${errMsg}`, error: true }])
      toast.error('Chat error')
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-200 flex-shrink-0">
        <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
          <MessageSquare size={16} className="text-white" />
        </div>
        <div>
          <p className="text-sm font-bold text-slate-900">Knowledge Base Chat</p>
          <p className="text-xs text-slate-400">Ask anything about the uploaded documents</p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            {/* Avatar */}
            <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0
              ${msg.role === 'user' ? 'bg-blue-600' : 'bg-slate-200'}`}>
              {msg.role === 'user'
                ? <User size={14} className="text-white" />
                : <Bot size={14} className="text-slate-600" />}
            </div>

            {/* Bubble */}
            <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm
              ${msg.role === 'user'
                ? 'bg-blue-600 text-white rounded-tr-sm'
                : msg.error
                  ? 'bg-red-50 border border-red-200 text-red-800 rounded-tl-sm'
                  : 'bg-white border border-slate-200 text-slate-800 rounded-tl-sm shadow-sm'}`}>
              {msg.role === 'user' ? (
                <p className="leading-relaxed whitespace-pre-wrap">{msg.content}</p>
              ) : (
                <div className="prose-cim text-sm">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center flex-shrink-0">
              <Bot size={14} className="text-slate-600" />
            </div>
            <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
              <div className="flex gap-1.5">
                <span className="w-2 h-2 rounded-full bg-slate-400 animate-bounce [animation-delay:-0.3s]" />
                <span className="w-2 h-2 rounded-full bg-slate-400 animate-bounce [animation-delay:-0.15s]" />
                <span className="w-2 h-2 rounded-full bg-slate-400 animate-bounce" />
              </div>
            </div>
          </div>
        )}

        <div ref={endRef} />
      </div>

      {/* Suggested questions */}
      {messages.length <= 1 && (
        <div className="px-4 pb-3 flex-shrink-0">
          <p className="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wide">Suggested questions</p>
          <div className="grid grid-cols-1 gap-1.5 max-h-40 overflow-y-auto">
            {SUGGESTED_QUESTIONS.map((q, i) => (
              <button
                key={i}
                onClick={() => sendMessage(q)}
                className="text-left text-xs px-3 py-2 bg-slate-50 hover:bg-blue-50 hover:text-blue-700 rounded-lg border border-slate-200 hover:border-blue-200 transition-all text-slate-600 truncate"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="px-4 pb-4 pt-2 border-t border-slate-200 flex-shrink-0">
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask a question about the documents..."
            rows={1}
            className="flex-1 input-field resize-none py-2.5 leading-5 min-h-[44px] max-h-32"
            style={{ overflowY: 'hidden', height: 'auto' }}
            onInput={e => { e.target.style.height = 'auto'; e.target.style.height = e.target.scrollHeight + 'px' }}
          />
          <button
            onClick={() => sendMessage()}
            disabled={loading || !input.trim()}
            className="btn-primary px-3 py-2.5 flex-shrink-0 self-end"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          </button>
        </div>
        <p className="text-xs text-slate-400 mt-1.5">Press Enter to send, Shift+Enter for newline</p>
      </div>
    </div>
  )
}
