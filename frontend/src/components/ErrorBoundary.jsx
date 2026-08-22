import { Component } from 'react'
import { AlertTriangle } from 'lucide-react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('Unhandled UI error:', error, info)
  }

  render() {
    if (!this.state.error) return this.props.children

    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-6">
        <div className="max-w-md text-center space-y-4">
          <div className="w-14 h-14 rounded-full bg-red-100 flex items-center justify-center mx-auto">
            <AlertTriangle className="text-red-600" size={26} />
          </div>
          <h1 className="text-lg font-bold text-slate-900">Something went wrong</h1>
          <p className="text-sm text-slate-500">
            The app hit an unexpected error. Reloading usually fixes it; your session and
            documents are unaffected.
          </p>
          <button onClick={() => window.location.reload()} className="btn-primary mx-auto">
            Reload
          </button>
        </div>
      </div>
    )
  }
}
