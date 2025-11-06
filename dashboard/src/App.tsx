import { useState, useEffect, lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Header from './components/Header'
import AgentsList from './pages/AgentsList'
import AgentDetail from './pages/AgentDetail'
import './styles/globals.css'

// Lazy load the metrics dashboard
const MetricsDashboard = lazy(() => import('./pages/MetricsDashboard'))

function App() {
  const [isDarkMode, setIsDarkMode] = useState(false)

  useEffect(() => {
    // Check for saved preference or system preference
    const savedMode = localStorage.getItem('darkMode')
    if (savedMode !== null) {
      setIsDarkMode(JSON.parse(savedMode))
    } else {
      setIsDarkMode(window.matchMedia('(prefers-color-scheme: dark)').matches)
    }
  }, [])

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
    <BrowserRouter>
      <div className="min-h-screen bg-white dark:bg-slate-900 text-navy-900 dark:text-slate-100 transition-colors">
        <Header isDarkMode={isDarkMode} onToggleDarkMode={toggleDarkMode} />
        <main className="container mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={<AgentsList />} />
            <Route path="/agents/:agentName" element={<AgentDetail />} />
            <Route
              path="/metrics"
              element={
                <Suspense
                  fallback={
                    <div className="flex items-center justify-center min-h-screen">
                      <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-navy-500 border-t-transparent"></div>
                    </div>
                  }
                >
                  <MetricsDashboard />
                </Suspense>
              }
            />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
