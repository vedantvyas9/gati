import { useState, useEffect, Suspense, lazy } from 'react'
import { Run, ExecutionTraceResponseData, ExecutionTreeNodeResponse } from '../types'
import { apiClient } from '../services/api'
import ExecutionTree from './ExecutionTree'
import EventDetailPanel from './EventDetailPanel'
import ErrorBoundary from './ErrorBoundary'

// Lazy load FlowGraph since it requires ReactFlow
const FlowGraph = lazy(() => import('./FlowGraph'))

interface RunDetailProps {
  run: Run
}

export default function RunDetail({ run }: RunDetailProps) {
  const [timeline, setTimeline] = useState<ExecutionTraceResponseData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedEvent, setSelectedEvent] = useState<ExecutionTreeNodeResponse | null>(null)
  const [showGraph, setShowGraph] = useState(true)
  const [isPanelOpen, setIsPanelOpen] = useState(false)

  useEffect(() => {
    const fetchTimeline = async () => {
      try {
        setLoading(true)
        const data = await apiClient.fetchRunTrace(run.agent_name, run.run_name)
        setTimeline(data)
        setError(null)
      } catch (err) {
        console.error('Failed to fetch run timeline:', err)
        setError('Failed to load run timeline.')
      } finally {
        setLoading(false)
      }
    }

    fetchTimeline()
  }, [run.agent_name, run.run_name])

  const handleEventSelect = (event: ExecutionTreeNodeResponse) => {
    setSelectedEvent(event)
    setIsPanelOpen(true)
  }

  const durationSeconds = (run?.total_duration_ms || 0) / 1000
  const durationMinutes = (durationSeconds / 60).toFixed(2)

  if (!run) {
    return (
      <div className="card text-center py-12">
        <p className="text-gray-600 dark:text-gray-400">No run selected</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Run Header - Compact */}
      <div className="card py-3 px-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-serif font-bold text-navy-900 dark:text-white">
              Run Details
            </h2>
            <div
              className={`px-2 py-0.5 rounded text-xs font-medium badge ${
                run.status === 'completed'
                  ? 'badge-success'
                  : run.status === 'failed'
                  ? 'badge-error'
                  : 'badge-info'
              }`}
            >
              {run.status.charAt(0).toUpperCase() + run.status.slice(1)}
            </div>
          </div>
          <p className="text-sm text-navy-600 dark:text-navy-400 font-semibold">
            {run.run_name}
          </p>
        </div>

        {/* Metrics - Compact horizontal layout */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-600 dark:text-gray-400">Duration:</span>
            <span className="text-sm font-semibold text-navy-600 dark:text-navy-400">
              {durationSeconds < 60
                ? `${durationSeconds.toFixed(1)}s`
                : `${durationMinutes}m`}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-600 dark:text-gray-400">Cost:</span>
            <span className="text-sm font-semibold text-navy-600 dark:text-navy-400">
              ${(run.total_cost || 0).toFixed(4)}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-600 dark:text-gray-400">Events:</span>
            <span className="text-sm font-semibold text-navy-600 dark:text-navy-400">
              {run.event_count || 0}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-600 dark:text-gray-400">Tokens:</span>
            <span className="text-sm font-semibold text-navy-600 dark:text-navy-400">
              {(((run.tokens_in || 0) + (run.tokens_out || 0)) / 1000).toFixed(1)}K
            </span>
          </div>
        </div>
      </div>

      {/* Execution Trace */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-serif font-bold text-navy-900 dark:text-white">
            Execution Trace
          </h3>
          <button
            onClick={() => setShowGraph(!showGraph)}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-all flex items-center gap-2 ${
              showGraph
                ? 'bg-navy-600 dark:bg-navy-700 text-white hover:bg-navy-700 dark:hover:bg-navy-600'
                : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
            }`}
          >
            {showGraph ? (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                Graph View
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
                Tree Only
              </>
            )}
          </button>
        </div>

        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-navy-500 border-t-transparent"></div>
          </div>
        ) : error ? (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
            <p className="text-red-700 dark:text-red-300 text-sm">{error}</p>
          </div>
        ) : timeline && timeline.execution_tree.length > 0 ? (
          <div className={`flex gap-4 ${showGraph ? 'h-[700px]' : ''}`}>
            {/* Tree View */}
            <div className={`${showGraph ? 'w-1/2 overflow-y-auto pr-4 border-r border-gray-200 dark:border-gray-700' : 'w-full max-h-[800px] overflow-y-auto'}`}>
              <ExecutionTree
                nodes={timeline.execution_tree}
                onNodeSelect={handleEventSelect}
                selectedNodeId={selectedEvent?.event_id}
              />
            </div>

            {/* Graph View */}
            {showGraph && (
              <div className="w-1/2 bg-gray-50 dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                <Suspense
                  fallback={
                    <div className="w-full h-full flex items-center justify-center">
                      <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-navy-500 border-t-transparent"></div>
                    </div>
                  }
                >
                  <ErrorBoundary>
                    <FlowGraph
                      nodes={timeline.execution_tree}
                      onNodeSelect={handleEventSelect}
                      selectedNodeId={selectedEvent?.event_id}
                    />
                  </ErrorBoundary>
                </Suspense>
              </div>
            )}
          </div>
        ) : (
          <p className="text-gray-600 dark:text-gray-400 text-sm text-center py-8">
            No execution trace available
          </p>
        )}
      </div>

      {/* Event Detail Panel */}
      <EventDetailPanel
        event={selectedEvent}
        onClose={() => {
          setIsPanelOpen(false)
          setSelectedEvent(null)
        }}
        isOpen={isPanelOpen}
      />
    </div>
  )
}
