import { Event } from '../types'

interface TimelineProps {
  events: Event[]
}

export default function Timeline({ events }: TimelineProps) {
  if (events.length === 0) {
    return (
      <p className="text-gray-600 dark:text-gray-400 text-sm text-center py-8">
        No events to display
      </p>
    )
  }

  const getEventColor = (eventType: string) => {
    switch (eventType) {
      case 'llm_call':
        return 'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200'
      case 'tool_call':
        return 'bg-purple-100 dark:bg-purple-900 text-purple-800 dark:text-purple-200'
      case 'agent_start':
        return 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200'
      case 'agent_end':
        return 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200'
      case 'error':
        return 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200'
      default:
        return 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200'
    }
  }

  const getEventIcon = (eventType: string): string => {
    switch (eventType) {
      case 'llm_call':
        return 'LLM'
      case 'tool_call':
        return 'TOOL'
      case 'agent_start':
        return 'START'
      case 'agent_end':
        return 'END'
      case 'error':
        return 'ERR'
      default:
        return 'EVENT'
    }
  }

  return (
    <div className="space-y-4">
      {events.map((event, index) => (
        <div key={event.event_id} className="flex gap-4">
          {/* Timeline line and dot */}
          <div className="flex flex-col items-center">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center text-xs font-bold ${getEventColor(event.event_type)}`}>
              {getEventIcon(event.event_type)}
            </div>
            {index < events.length - 1 && (
              <div className="w-1 h-8 bg-gray-300 dark:bg-gray-600 mt-2"></div>
            )}
          </div>

          {/* Event content */}
          <div className="flex-1 pb-4">
            <div className="flex items-start justify-between">
              <div>
                <h4 className="font-semibold text-navy-900 dark:text-white">
                  {event.event_type.replace(/_/g, ' ').charAt(0).toUpperCase() + event.event_type.replace(/_/g, ' ').slice(1)}
                </h4>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  {new Date(event.timestamp).toLocaleTimeString()}
                </p>
              </div>
              {event.latency_ms && (
                <span className="text-xs px-2 py-1 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded">
                  {event.latency_ms}ms
                </span>
              )}
            </div>

            {/* Event data */}
            {Object.keys(event.data).length > 0 && (
              <div className="mt-2 bg-gray-50 dark:bg-gray-800 rounded p-3 text-sm">
                <pre className="text-gray-700 dark:text-gray-300 overflow-x-auto whitespace-pre-wrap break-words text-xs">
                  {JSON.stringify(event.data, null, 2).split('\n').slice(0, 10).join('\n')}
                  {JSON.stringify(event.data, null, 2).split('\n').length > 10 && '...'}
                </pre>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
