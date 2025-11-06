import { useState, useEffect } from 'react'
import { Run } from '../types'
import RunDetail from './RunDetail'

interface AgentRunsProps {
  runs: Run[]
  onDeleteRun: (agentName: string, runName: string) => void
}

export default function AgentRuns({ runs, onDeleteRun }: AgentRunsProps) {
  const [selectedRun, setSelectedRun] = useState<Run | null>(null)
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)

  // Set first run as selected when runs are loaded
  useEffect(() => {
    if (runs.length > 0 && !selectedRun) {
      setSelectedRun(runs[0])
    }
  }, [runs, selectedRun])

  return (
    <div className="flex gap-6 h-[calc(100vh-300px)] min-h-[600px]">
      {/* Runs Sidebar */}
      <div
        className={`transition-all duration-300 flex-shrink-0 ${
          isSidebarCollapsed ? 'w-12' : 'w-80'
        }`}
      >
        <div className="card h-full flex flex-col">
          <div className="flex items-center justify-between mb-4">
            {!isSidebarCollapsed && (
              <h2 className="text-xl font-serif font-bold text-navy-900 dark:text-white">
                Runs
              </h2>
            )}
            <button
              onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded transition-colors"
              title={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              <svg
                className={`w-5 h-5 text-gray-600 dark:text-gray-400 transition-transform ${
                  isSidebarCollapsed ? 'rotate-180' : ''
                }`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M11 19l-7-7 7-7m8 14l-7-7 7-7"
                />
              </svg>
            </button>
          </div>

          {!isSidebarCollapsed && (
            <>
              {runs.length === 0 ? (
                <p className="text-gray-600 dark:text-gray-400 text-sm">No runs yet</p>
              ) : (
                <div className="space-y-2 overflow-y-auto flex-1">
                  {runs.map((run) => (
                    <div
                      key={`${run.agent_name}-${run.run_name}`}
                      className={`flex items-start justify-between p-3 rounded-lg transition-colors cursor-pointer ${
                        selectedRun?.run_name === run.run_name && selectedRun?.agent_name === run.agent_name
                          ? 'bg-navy-100 dark:bg-navy-800 border-2 border-navy-300 dark:border-navy-600'
                          : 'hover:bg-gray-100 dark:hover:bg-gray-800 border-2 border-transparent'
                      }`}
                    >
                      <button
                        onClick={() => setSelectedRun(run)}
                        className="flex-1 text-left"
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-semibold text-navy-900 dark:text-navy-100">
                            {run.run_name}
                          </span>
                          <span
                            className={`text-xs px-2 py-1 rounded badge ${
                              run.status === 'completed'
                                ? 'badge-success'
                                : run.status === 'failed'
                                ? 'badge-error'
                                : 'badge-info'
                            }`}
                          >
                            {run.status}
                          </span>
                        </div>
                        <p className="text-xs text-gray-600 dark:text-gray-400">
                          {new Date(run.created_at).toLocaleString()}
                        </p>
                        <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                          Cost: ${(run.total_cost || 0).toFixed(2)}
                        </p>
                      </button>
                      <button
                        onClick={() => onDeleteRun(run.agent_name, run.run_name)}
                        className="ml-2 p-1.5 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors flex-shrink-0"
                        title="Delete run"
                      >
                        <svg
                          className="w-4 h-4"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                          />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Run Detail */}
      <div className="flex-1 overflow-y-auto">
        {selectedRun ? (
          <RunDetail run={selectedRun} />
        ) : (
          <div className="card text-center py-12">
            <p className="text-gray-600 dark:text-gray-400">
              Select a run to view details
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
