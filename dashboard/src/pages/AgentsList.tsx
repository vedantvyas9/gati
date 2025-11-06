import { useState, useEffect, useCallback } from 'react'
import AgentCard from '../components/AgentCard'
import RealtimeIndicator from '../components/RealtimeIndicator'
import { Agent } from '../types'
import { apiClient } from '../services/api'
import { usePolling } from '../hooks/usePolling'

export default function AgentsList() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [enablePolling, setEnablePolling] = useState(true)

  const fetchAgents = useCallback(async () => {
    try {
      const data = await apiClient.fetchAgents()
      setAgents(data)
      setError(null)
    } catch (err) {
      console.error('Failed to fetch agents:', err)
      setError('Failed to load agents. Make sure the API server is running.')
      setAgents([])
    }
  }, [])

  // Initial fetch
  useEffect(() => {
    const initialFetch = async () => {
      setLoading(true)
      await fetchAgents()
      setLoading(false)
    }

    initialFetch()
  }, [fetchAgents])

  // Setup polling for real-time updates
  const { lastUpdated } = usePolling(fetchAgents, {
    interval: 5000,
    enabled: enablePolling && !loading && !error,
  })

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-navy-500 border-t-transparent mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading agents...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6">
        <h3 className="text-red-800 dark:text-red-200 font-bold mb-2">Error</h3>
        <p className="text-red-700 dark:text-red-300">{error}</p>
      </div>
    )
  }

  const handleAgentDelete = (agentName: string) => {
    setAgents((prev) => prev.filter((agent) => agent.name !== agentName))
  }

  if (agents.length === 0) {
    return (
      <div className="text-center py-12">
        <div className="text-6xl mb-4">📊</div>
        <h2 className="text-2xl font-serif font-bold text-navy-900 dark:text-white mb-2">
          No Agents Yet
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mb-6">
          Once you start running agents, they will appear here.
        </p>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-8 flex items-start justify-between">
        <div>
          <h2 className="text-3xl font-serif font-bold text-navy-900 dark:text-white mb-2">
            Agents
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            Monitor and manage your AI agents
          </p>
        </div>
        <div className="flex items-center gap-4">
          <RealtimeIndicator isActive={enablePolling} lastUpdated={lastUpdated} />
          <button
            onClick={() => setEnablePolling(!enablePolling)}
            className="px-3 py-2 text-sm bg-navy-50 dark:bg-navy-900/50 text-navy-600 dark:text-navy-300 rounded hover:bg-navy-100 dark:hover:bg-navy-900 transition-colors font-medium"
            title={enablePolling ? 'Pause updates' : 'Resume updates'}
          >
            {enablePolling ? 'Live' : 'Paused'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {agents.map((agent) => (
          <AgentCard
            key={agent.name}
            agent={agent}
            onDelete={handleAgentDelete}
          />
        ))}
      </div>
    </div>
  )
}
