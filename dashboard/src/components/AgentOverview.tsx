import { Agent } from '../types'

interface AgentOverviewProps {
  agent: Agent
}

export default function AgentOverview({ agent }: AgentOverviewProps) {
  return (
    <div className="space-y-6">
      {/* Agent Information */}
      <div className="card">
        <h2 className="text-xl font-serif font-bold text-navy-900 dark:text-white mb-4">
          Agent Information
        </h2>
        <div className="space-y-4">
          <div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Name</p>
            <p className="text-lg font-semibold text-navy-900 dark:text-white">
              {agent.name}
            </p>
          </div>
          {agent.description && (
            <div>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Description</p>
              <p className="text-gray-700 dark:text-gray-300">{agent.description}</p>
            </div>
          )}
          <div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Created</p>
            <p className="text-gray-700 dark:text-gray-300">
              {new Date(agent.created_at).toLocaleString()}
            </p>
          </div>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="card">
        <h2 className="text-xl font-serif font-bold text-navy-900 dark:text-white mb-4">
          Quick Statistics
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 border border-blue-200 dark:border-blue-800">
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Total Runs</p>
            <p className="text-3xl font-bold text-blue-600 dark:text-blue-400">
              {agent.total_runs || 0}
            </p>
          </div>
          <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-4 border border-purple-200 dark:border-purple-800">
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Total Events</p>
            <p className="text-3xl font-bold text-purple-600 dark:text-purple-400">
              {agent.total_events || 0}
            </p>
          </div>
          <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-4 border border-green-200 dark:border-green-800">
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Total Cost</p>
            <p className="text-3xl font-bold text-green-600 dark:text-green-400">
              ${(agent.total_cost || 0).toFixed(2)}
            </p>
          </div>
          <div className="bg-orange-50 dark:bg-orange-900/20 rounded-lg p-4 border border-orange-200 dark:border-orange-800">
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Avg Cost/Run</p>
            <p className="text-3xl font-bold text-orange-600 dark:text-orange-400">
              ${(agent.avg_cost || 0).toFixed(2)}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
