import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Agent, Run } from '../types'
import { apiClient } from '../services/api'
import AgentOverview from '../components/AgentOverview'
import AgentRuns from '../components/AgentRuns'
import ConfirmationModal from '../components/ConfirmationModal'
import RealtimeIndicator from '../components/RealtimeIndicator'
import { usePolling } from '../hooks/usePolling'

type TabType = 'overview' | 'runs'

export default function AgentDetail() {
  const { agentName } = useParams<{ agentName: string }>()
  const navigate = useNavigate()
  const [agent, setAgent] = useState<Agent | null>(null)
  const [runs, setRuns] = useState<Run[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [enablePolling, setEnablePolling] = useState(true)
  const [activeTab, setActiveTab] = useState<TabType>('overview')
  const [deleteRunModal, setDeleteRunModal] = useState<{ isOpen: boolean; agentName: string | null; runName: string | null }>({
    isOpen: false,
    agentName: null,
    runName: null,
  })
  const [isDeletingRun, setIsDeletingRun] = useState(false)

  const fetchData = useCallback(async () => {
    if (!agentName) {
      setError('Agent name not found in URL parameters.')
      setLoading(false)
      return
    }

    try {
      const [agentData, runsData] = await Promise.all([
        apiClient.fetchAgentDetails(agentName),
        apiClient.fetchAgentRuns(agentName),
      ])
      setAgent(agentData)
      setRuns(runsData)
      setError(null)
    } catch (err) {
      console.error('Failed to fetch agent details:', err)
      setError('Failed to load agent details.')
    }
  }, [agentName])

  // Initial fetch
  useEffect(() => {
    const initialFetch = async () => {
      setLoading(true)
      await fetchData()
      setLoading(false)
    }

    initialFetch()
  }, [agentName, fetchData])

  // Setup polling for real-time updates (every 5 seconds for active runs)
  const { lastUpdated } = usePolling(fetchData, {
    interval: 5000,
    enabled: enablePolling && !loading && !error && activeTab === 'runs',
  })

  const handleDeleteRun = (agentName: string, runName: string) => {
    setDeleteRunModal({ isOpen: true, agentName, runName })
  }

  const handleConfirmDeleteRun = async () => {
    if (!deleteRunModal.agentName || !deleteRunModal.runName) return

    try {
      setIsDeletingRun(true)
      await apiClient.deleteRun(deleteRunModal.agentName, deleteRunModal.runName)
      setRuns((prev) => prev.filter((run) =>
        !(run.agent_name === deleteRunModal.agentName && run.run_name === deleteRunModal.runName)
      ))
      setDeleteRunModal({ isOpen: false, agentName: null, runName: null })
    } catch (error) {
      console.error('Failed to delete run:', error)
      alert('Failed to delete run. Please try again.')
    } finally {
      setIsDeletingRun(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-navy-500 border-t-transparent mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading agent details...</p>
        </div>
      </div>
    )
  }

  if (error || !agent) {
    return (
      <div>
        <button
          onClick={() => navigate('/')}
          className="flex items-center space-x-2 text-navy-600 dark:text-navy-400 hover:text-navy-700 dark:hover:text-navy-300 mb-6 font-medium"
        >
          <span>←</span>
          <span>Back to Agents</span>
        </button>
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6">
          <h3 className="text-red-800 dark:text-red-200 font-bold mb-2">Error</h3>
          <p className="text-red-700 dark:text-red-300">
            {error || (!agentName ? 'Agent name not found in URL' : 'Agent not found.')}
          </p>
          {error && (
            <p className="text-xs text-red-600 dark:text-red-400 mt-2 font-mono">
              {error}
            </p>
          )}
        </div>
      </div>
    )
  }

  const tabs: { id: TabType; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'runs', label: 'Runs' },
  ]

  return (
    <div>
      {/* Back button */}
      <button
        onClick={() => navigate('/')}
        className="flex items-center space-x-2 text-navy-600 dark:text-navy-400 hover:text-navy-700 dark:hover:text-navy-300 mb-6 font-medium"
      >
        <span>←</span>
        <span>Back to Agents</span>
      </button>

      {/* Agent header */}
      <div className="card mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-4xl font-serif font-bold text-navy-900 dark:text-white mb-2">
              {agent.name}
            </h1>
            {agent.description && (
              <p className="text-gray-600 dark:text-gray-400">{agent.description}</p>
            )}
          </div>
          <div className="flex flex-col items-end gap-3">
            {activeTab === 'runs' && (
              <>
                <RealtimeIndicator isActive={enablePolling} lastUpdated={lastUpdated} />
                <button
                  onClick={() => setEnablePolling(!enablePolling)}
                  className="px-3 py-2 text-sm bg-navy-50 dark:bg-navy-900/50 text-navy-600 dark:text-navy-300 rounded hover:bg-navy-100 dark:hover:bg-navy-900 transition-colors font-medium"
                  title={enablePolling ? 'Pause updates' : 'Resume updates'}
                >
                  {enablePolling ? 'Live' : 'Paused'}
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-6">
        <nav className="-mb-px flex space-x-8">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === tab.id
                  ? 'border-navy-500 text-navy-600 dark:text-navy-400'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div>
        {activeTab === 'overview' && <AgentOverview agent={agent} />}
        {activeTab === 'runs' && <AgentRuns runs={runs} onDeleteRun={handleDeleteRun} />}
      </div>

      <ConfirmationModal
        isOpen={deleteRunModal.isOpen}
        title="Delete Run"
        message="Are you sure? This action cannot be undone. The run and all its events will be permanently deleted."
        confirmText="Delete"
        cancelText="Cancel"
        isDangerous
        isLoading={isDeletingRun}
        onConfirm={handleConfirmDeleteRun}
        onCancel={() => setDeleteRunModal({ isOpen: false, agentName: null, runName: null })}
      />
    </div>
  )
}
