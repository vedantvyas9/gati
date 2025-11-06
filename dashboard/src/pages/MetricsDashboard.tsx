import { useState, useEffect } from 'react'
import {
  MetricsSummary,
  CostTimestampData,
  TokensTimestampData,
  AgentComparisonData,
} from '../types'
import { apiClient } from '../services/api'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

interface DashboardState {
  metrics: MetricsSummary | null
  costTimeline: CostTimestampData[]
  tokensTimeline: TokensTimestampData[]
  agentsComparison: AgentComparisonData[]
  loading: boolean
  error: string | null
}

export default function MetricsDashboard() {
  const [state, setState] = useState<DashboardState>({
    metrics: null,
    costTimeline: [],
    tokensTimeline: [],
    agentsComparison: [],
    loading: false,
    error: null,
  })
  const [days, setDays] = useState(30)

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        setState((prev) => ({ ...prev, loading: true, error: null }))

        const [metrics, costTimeline, tokensTimeline, agentsComparison] =
          await Promise.all([
            apiClient.fetchMetrics(),
            apiClient.fetchCostTimeline(days),
            apiClient.fetchTokensTimeline(days),
            apiClient.fetchAgentsComparison(),
          ])

        setState({
          metrics,
          costTimeline,
          tokensTimeline,
          agentsComparison,
          loading: false,
          error: null,
        })
      } catch (err) {
        console.error('Failed to fetch metrics:', err)
        setState((prev) => ({
          ...prev,
          loading: false,
          error: 'Failed to load metrics. Please try again.',
        }))
      }
    }

    fetchMetrics()
  }, [days])

  if (state.loading && !state.metrics) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-navy-500 border-t-transparent"></div>
      </div>
    )
  }

  if (state.error && !state.metrics) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
        <div className="max-w-7xl mx-auto">
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6">
            <p className="text-red-700 dark:text-red-300">{state.error}</p>
          </div>
        </div>
      </div>
    )
  }

  const metrics = state.metrics

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-serif font-bold text-navy-900 dark:text-white">
              Metrics Dashboard
            </h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Global view of all agents and runs
            </p>
          </div>

          {/* Date Range Selector */}
          <div className="flex gap-2">
            {[7, 14, 30, 60, 90].map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`px-4 py-2 rounded-lg font-medium transition-all ${
                  days === d
                    ? 'bg-navy-600 dark:bg-navy-700 text-white'
                    : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-700 hover:border-navy-500 dark:hover:border-navy-500'
                }`}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>

        {/* Summary Cards */}
        {metrics && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                Total Agents
              </p>
              <p className="text-3xl font-bold text-navy-600 dark:text-navy-400">
                {metrics.total_agents}
              </p>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                Total Runs
              </p>
              <p className="text-3xl font-bold text-navy-600 dark:text-navy-400">
                {metrics.total_runs}
              </p>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                Total Events
              </p>
              <p className="text-3xl font-bold text-navy-600 dark:text-navy-400">
                {metrics.total_events.toLocaleString()}
              </p>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                Total Cost
              </p>
              <p className="text-3xl font-bold text-green-600 dark:text-green-400">
                ${metrics.total_cost.toFixed(2)}
              </p>
            </div>

            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                Avg Cost/Run
              </p>
              <p className="text-3xl font-bold text-purple-600 dark:text-purple-400">
                ${metrics.avg_cost_per_run.toFixed(4)}
              </p>
            </div>
          </div>
        )}

        {/* Charts Row 1 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Cost Timeline */}
          {state.costTimeline.length > 0 && (
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
              <h2 className="text-lg font-serif font-bold text-navy-900 dark:text-white mb-4">
                Cost Over Time
              </h2>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={state.costTimeline}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                  <XAxis
                    dataKey="timestamp"
                    tick={{ fontSize: 12 }}
                    stroke="#9CA3AF"
                  />
                  <YAxis tick={{ fontSize: 12 }} stroke="#9CA3AF" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1F2937',
                      border: '1px solid #374151',
                      borderRadius: '8px',
                      color: '#F3F4F6',
                    }}
                  />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="cost"
                    stroke="#3B82F6"
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="cumulative_cost"
                    stroke="#10B981"
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Tokens Timeline */}
          {state.tokensTimeline.length > 0 && (
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
              <h2 className="text-lg font-serif font-bold text-navy-900 dark:text-white mb-4">
                Token Usage Over Time
              </h2>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={state.tokensTimeline}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                  <XAxis
                    dataKey="timestamp"
                    tick={{ fontSize: 12 }}
                    stroke="#9CA3AF"
                  />
                  <YAxis tick={{ fontSize: 12 }} stroke="#9CA3AF" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1F2937',
                      border: '1px solid #374151',
                      borderRadius: '8px',
                      color: '#F3F4F6',
                    }}
                  />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="tokens_in"
                    stroke="#8B5CF6"
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="tokens_out"
                    stroke="#F59E0B"
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* Charts Row 2 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Runs Per Agent */}
          {state.agentsComparison.length > 0 && (
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
              <h2 className="text-lg font-serif font-bold text-navy-900 dark:text-white mb-4">
                Runs Per Agent
              </h2>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={state.agentsComparison}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                  <XAxis
                    dataKey="agent_name"
                    tick={{ fontSize: 12 }}
                    stroke="#9CA3AF"
                  />
                  <YAxis tick={{ fontSize: 12 }} stroke="#9CA3AF" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1F2937',
                      border: '1px solid #374151',
                      borderRadius: '8px',
                      color: '#F3F4F6',
                    }}
                  />
                  <Bar
                    dataKey="runs"
                    fill="#3B82F6"
                    isAnimationActive={false}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Cost Per Agent */}
          {state.agentsComparison.length > 0 && (
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
              <h2 className="text-lg font-serif font-bold text-navy-900 dark:text-white mb-4">
                Cost Per Agent
              </h2>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={state.agentsComparison}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                  <XAxis
                    dataKey="agent_name"
                    tick={{ fontSize: 12 }}
                    stroke="#9CA3AF"
                  />
                  <YAxis tick={{ fontSize: 12 }} stroke="#9CA3AF" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1F2937',
                      border: '1px solid #374151',
                      borderRadius: '8px',
                      color: '#F3F4F6',
                    }}
                  />
                  <Bar
                    dataKey="cost"
                    fill="#10B981"
                    isAnimationActive={false}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* Tables Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Top Agents by Cost Table */}
          {metrics && metrics.top_agents_by_cost.length > 0 && (
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
              <h2 className="text-lg font-serif font-bold text-navy-900 dark:text-white mb-4">
                Top Agents by Cost
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 dark:border-gray-700">
                      <th className="text-left py-2 text-gray-600 dark:text-gray-400 font-semibold">
                        Agent
                      </th>
                      <th className="text-right py-2 text-gray-600 dark:text-gray-400 font-semibold">
                        Cost
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {metrics.top_agents_by_cost.map((agent) => (
                      <tr
                        key={agent.agent_name}
                        className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50"
                      >
                        <td className="py-3 text-gray-900 dark:text-gray-100">
                          {agent.agent_name}
                        </td>
                        <td className="py-3 text-right font-mono text-green-600 dark:text-green-400 font-bold">
                          ${agent.cost.toFixed(4)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Top Agents by Runs Table */}
          {metrics && metrics.top_agents_by_runs.length > 0 && (
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
              <h2 className="text-lg font-serif font-bold text-navy-900 dark:text-white mb-4">
                Top Agents by Runs
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 dark:border-gray-700">
                      <th className="text-left py-2 text-gray-600 dark:text-gray-400 font-semibold">
                        Agent
                      </th>
                      <th className="text-right py-2 text-gray-600 dark:text-gray-400 font-semibold">
                        Runs
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {metrics.top_agents_by_runs.map((agent) => (
                      <tr
                        key={agent.agent_name}
                        className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50"
                      >
                        <td className="py-3 text-gray-900 dark:text-gray-100">
                          {agent.agent_name}
                        </td>
                        <td className="py-3 text-right font-mono text-blue-600 dark:text-blue-400 font-bold">
                          {agent.runs}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Agent Comparison Table */}
        {state.agentsComparison.length > 0 && (
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border border-gray-200 dark:border-gray-700">
            <h2 className="text-lg font-serif font-bold text-navy-900 dark:text-white mb-4">
              Agent Comparison
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left py-3 text-gray-600 dark:text-gray-400 font-semibold">
                      Agent Name
                    </th>
                    <th className="text-right py-3 text-gray-600 dark:text-gray-400 font-semibold">
                      Runs
                    </th>
                    <th className="text-right py-3 text-gray-600 dark:text-gray-400 font-semibold">
                      Total Cost
                    </th>
                    <th className="text-right py-3 text-gray-600 dark:text-gray-400 font-semibold">
                      Avg Cost
                    </th>
                    <th className="text-right py-3 text-gray-600 dark:text-gray-400 font-semibold">
                      Total Tokens
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {state.agentsComparison.map((agent) => (
                    <tr
                      key={agent.agent_name}
                      className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50"
                    >
                      <td className="py-3 text-gray-900 dark:text-gray-100 font-medium">
                        {agent.agent_name}
                      </td>
                      <td className="py-3 text-right font-mono text-blue-600 dark:text-blue-400">
                        {agent.runs}
                      </td>
                      <td className="py-3 text-right font-mono text-green-600 dark:text-green-400 font-bold">
                        ${agent.cost.toFixed(4)}
                      </td>
                      <td className="py-3 text-right font-mono text-purple-600 dark:text-purple-400">
                        ${agent.avg_cost_per_run.toFixed(6)}
                      </td>
                      <td className="py-3 text-right font-mono text-orange-600 dark:text-orange-400">
                        {Math.round(agent.total_tokens).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
