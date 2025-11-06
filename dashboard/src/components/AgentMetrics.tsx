import { Agent } from '../types'

interface AgentMetricsProps {
  agent: Agent
}

export default function AgentMetrics({ agent }: AgentMetricsProps) {
  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card">
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Total Runs</p>
          <p className="text-3xl font-bold text-navy-600 dark:text-navy-400">
            {agent.total_runs || 0}
          </p>
        </div>
        <div className="card">
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Total Events</p>
          <p className="text-3xl font-bold text-navy-600 dark:text-navy-400">
            {agent.total_events || 0}
          </p>
        </div>
        <div className="card">
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Total Cost</p>
          <p className="text-3xl font-bold text-navy-600 dark:text-navy-400">
            ${(agent.total_cost || 0).toFixed(2)}
          </p>
        </div>
        <div className="card">
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Avg Cost/Run</p>
          <p className="text-3xl font-bold text-navy-600 dark:text-navy-400">
            ${(agent.avg_cost || 0).toFixed(2)}
          </p>
        </div>
      </div>

      {/* Placeholder for visualizations */}
      <div className="card">
        <h2 className="text-xl font-serif font-bold text-navy-900 dark:text-white mb-4">
          Tool Calls Over Time
        </h2>
        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-8 text-center">
          <p className="text-gray-600 dark:text-gray-400">
            Visualization coming soon - Line graph showing tool calls per run
          </p>
        </div>
      </div>

      <div className="card">
        <h2 className="text-xl font-serif font-bold text-navy-900 dark:text-white mb-4">
          Cost Per Run
        </h2>
        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-8 text-center">
          <p className="text-gray-600 dark:text-gray-400">
            Visualization coming soon - Bar chart showing cost breakdown by run
          </p>
        </div>
      </div>

      <div className="card">
        <h2 className="text-xl font-serif font-bold text-navy-900 dark:text-white mb-4">
          Event Type Distribution
        </h2>
        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-8 text-center">
          <p className="text-gray-600 dark:text-gray-400">
            Visualization coming soon - Pie chart showing event type distribution
          </p>
        </div>
      </div>
    </div>
  )
}
