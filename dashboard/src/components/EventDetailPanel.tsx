import React from 'react'
import { ExecutionTreeNodeResponse } from '../types'

interface EventDetailPanelProps {
  event: ExecutionTreeNodeResponse | null
  onClose: () => void
  isOpen: boolean
}

export default function EventDetailPanel({
  event,
  onClose,
  isOpen,
}: EventDetailPanelProps) {
  if (!isOpen || !event) return null

  const formatJsonValue = (value: unknown): React.ReactNode => {
    if (value === null || value === undefined) return 'null'
    if (typeof value === 'string') return value
    if (typeof value === 'number') return value.toString()
    if (typeof value === 'boolean') return value ? 'true' : 'false'
    return JSON.stringify(value, null, 2)
  }


  return (
    <div className="fixed inset-0 bg-black/50 dark:bg-black/70 z-50 flex items-end sm:items-center sm:justify-center">
      <div className="bg-white dark:bg-gray-800 w-full sm:max-w-2xl max-h-[90vh] sm:rounded-lg shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
          <div>
            <h2 className="text-xl font-serif font-bold text-navy-900 dark:text-white">
              Event Details
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 font-mono mt-1">
              {event.event_id}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors"
          >
            <svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="overflow-y-auto flex-1">
          <div className="p-6 space-y-6">
            {/* Event Type & Metadata */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-gray-600 dark:text-gray-400 mb-2 font-semibold">
                  Event Type
                </p>
                <p className="text-sm font-mono text-navy-600 dark:text-navy-400">
                  {event.event_type}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-600 dark:text-gray-400 mb-2 font-semibold">
                  Timestamp
                </p>
                <p className="text-sm text-navy-600 dark:text-navy-400">
                  {new Date(event.timestamp).toLocaleString()}
                </p>
              </div>
            </div>

            {/* Metrics */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {([
                event.latency_ms !== undefined && event.latency_ms !== null ? (
                  <div key="latency" className="bg-blue-50 dark:bg-blue-900/30 rounded-lg p-3 border border-blue-200 dark:border-blue-700">
                    <p className="text-xs text-gray-600 dark:text-gray-400 font-semibold mb-1">
                      Latency
                    </p>
                    <p className="text-sm font-bold text-blue-700 dark:text-blue-300">
                      {event.latency_ms < 1000
                        ? `${event.latency_ms.toFixed(0)}ms`
                        : `${(event.latency_ms / 1000).toFixed(2)}s`}
                    </p>
                  </div>
                ) : null,
                event.cost !== undefined && event.cost !== null ? (
                  <div key="cost" className="bg-green-50 dark:bg-green-900/30 rounded-lg p-3 border border-green-200 dark:border-green-700">
                    <p className="text-xs text-gray-600 dark:text-gray-400 font-semibold mb-1">
                      Cost
                    </p>
                    <p className="text-sm font-bold text-green-700 dark:text-green-300">
                      ${event.cost.toFixed(4)}
                    </p>
                  </div>
                ) : null,
                event.tokens_in !== undefined && event.tokens_in !== null ? (
                  <div key="tokens_in" className="bg-purple-50 dark:bg-purple-900/30 rounded-lg p-3 border border-purple-200 dark:border-purple-700">
                    <p className="text-xs text-gray-600 dark:text-gray-400 font-semibold mb-1">
                      Tokens In
                    </p>
                    <p className="text-sm font-bold text-purple-700 dark:text-purple-300">
                      {Math.round(event.tokens_in)}
                    </p>
                  </div>
                ) : null,
                event.tokens_out !== undefined && event.tokens_out !== null ? (
                  <div key="tokens_out" className="bg-orange-50 dark:bg-orange-900/30 rounded-lg p-3 border border-orange-200 dark:border-orange-700">
                    <p className="text-xs text-gray-600 dark:text-gray-400 font-semibold mb-1">
                      Tokens Out
                    </p>
                    <p className="text-sm font-bold text-orange-700 dark:text-orange-300">
                      {Math.round(event.tokens_out)}
                    </p>
                  </div>
                ) : null,
              ] as React.ReactNode[]).filter(Boolean)}
            </div>

            {/* Event Data */}
            <div>
              <p className="text-xs text-gray-600 dark:text-gray-400 mb-3 font-semibold">
                Event Data
              </p>
              <div className="bg-gray-50 dark:bg-gray-900/50 rounded-lg p-4 border border-gray-200 dark:border-gray-700 overflow-x-auto">
                <pre className="text-xs font-mono text-gray-800 dark:text-gray-200 whitespace-pre-wrap break-words">
                  {JSON.stringify(event.data, null, 2)}
                </pre>
              </div>
            </div>

            {/* Request/Response Details */}
            {event.data?.prompt && (
              <div>
                <p className="text-xs text-gray-600 dark:text-gray-400 mb-2 font-semibold">
                  Prompt
                </p>
                <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 border border-blue-200 dark:border-blue-700">
                  <p className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap break-words font-mono text-xs">
                    {formatJsonValue(event.data.prompt)}
                  </p>
                </div>
              </div>
            )}

            {event.data?.completion && (
              <div>
                <p className="text-xs text-gray-600 dark:text-gray-400 mb-2 font-semibold">
                  Completion
                </p>
                <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-4 border border-green-200 dark:border-green-700">
                  <p className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap break-words font-mono text-xs">
                    {formatJsonValue(event.data.completion)}
                  </p>
                </div>
              </div>
            )}

            {event.data?.error && (
              <div>
                <p className="text-xs text-gray-600 dark:text-gray-400 mb-2 font-semibold">
                  Error
                </p>
                <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-4 border border-red-200 dark:border-red-700">
                  <p className="text-sm text-red-700 dark:text-red-300 whitespace-pre-wrap break-words font-mono text-xs">
                    {formatJsonValue(event.data.error)}
                  </p>
                </div>
              </div>
            )}

            {/* Metadata Section */}
            <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
              <p className="text-xs text-gray-600 dark:text-gray-400 mb-3 font-semibold">
                Metadata
              </p>
              <div className="grid grid-cols-2 gap-4 text-sm">
                {event.parent_event_id && (
                  <div>
                    <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">
                      Parent Event
                    </p>
                    <p className="font-mono text-gray-700 dark:text-gray-300 text-xs break-all">
                      {event.parent_event_id}
                    </p>
                  </div>
                )}
                <div>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">
                    Agent Name
                  </p>
                  <p className="font-mono text-gray-700 dark:text-gray-300 text-xs">
                    {event.agent_name}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">
                    Run ID
                  </p>
                  <p className="font-mono text-gray-700 dark:text-gray-300 text-xs break-all">
                    {event.run_id}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 dark:border-gray-700 p-4 bg-gray-50 dark:bg-gray-900/50 flex-shrink-0">
          <button
            onClick={onClose}
            className="w-full px-4 py-2 bg-navy-600 hover:bg-navy-700 dark:bg-navy-700 dark:hover:bg-navy-600 text-white rounded-lg font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
