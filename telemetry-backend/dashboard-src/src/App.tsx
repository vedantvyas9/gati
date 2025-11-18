import { useState, useEffect } from 'react'
import './styles/globals.css'
import AnalyticsDashboard from './pages/AnalyticsDashboard'

function App() {
  // Initialize from localStorage synchronously to prevent flash
  const getInitialDarkMode = () => {
    const savedMode = localStorage.getItem('darkMode')
    if (savedMode !== null) {
      return JSON.parse(savedMode)
    }
    // Default to system preference if no saved preference
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  }

  const [isDarkMode, setIsDarkMode] = useState(getInitialDarkMode)

  useEffect(() => {
    // Update DOM and localStorage
    if (isDarkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
    localStorage.setItem('darkMode', JSON.stringify(isDarkMode))
  }, [isDarkMode])

  const toggleDarkMode = () => {
    setIsDarkMode(!isDarkMode)
  }

  return (
    <div className="min-h-screen bg-white dark:bg-slate-950 text-navy-900 dark:text-slate-100 transition-colors">
      <div className="max-w-6xl mx-auto px-4 py-10 space-y-10">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-navy-600 dark:text-navy-300 font-semibold">
              GATI Telemetry
            </p>
            <h1 className="text-2xl font-serif font-bold">Control Room</h1>
            <p className="text-slate-500 dark:text-slate-400">
              Live counts for installs, events, MCP queries, and tracked agents.
            </p>
          </div>
          <button
            onClick={toggleDarkMode}
            className="self-start inline-flex items-center gap-2 rounded-full border border-slate-300 dark:border-slate-700 px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-100 hover:bg-slate-50 dark:hover:bg-slate-900"
          >
            {isDarkMode ? 'Switch to Light' : 'Switch to Dark'}
            <span
              className={`h-2.5 w-2.5 rounded-full ${isDarkMode ? 'bg-yellow-400' : 'bg-slate-800'}`}
            />
          </button>
        </header>

        <main>
          <AnalyticsDashboard />
        </main>
      </div>
    </div>
  )
}

export default App

