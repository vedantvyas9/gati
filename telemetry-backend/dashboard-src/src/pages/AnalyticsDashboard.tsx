import { useState, useCallback, useEffect, ReactNode, useMemo } from 'react'
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { apiClient } from '../services/api'
import { usePolling } from '../hooks/usePolling'
import {
  AnalyticsTimeseriesPoint,
  AnalyticsTimeseriesResponse,
} from '../types'

const RANGE_OPTIONS = [
  { label: 'Last 7 days', value: 7 },
  { label: 'Last 30 days', value: 30 },
  { label: 'Last 90 days', value: 90 },
  { label: 'All time', value: 0 },
]

const tooltipStyles = {
  backgroundColor: '#0f172a',
  border: '1px solid #1e293b',
  borderRadius: '8px',
  color: '#e2e8f0',
}

function formatAxisDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

const ChartCard = ({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle?: string
  children: ReactNode
}) => (
  <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm">
    <div className="mb-4">
      <p className="text-sm uppercase tracking-wide text-slate-500 font-semibold">
        {title}
      </p>
      {subtitle && (
        <p className="text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>
      )}
    </div>
    {children}
  </div>
)

export default function AnalyticsDashboard() {
  const [selectedRange, setSelectedRange] = useState<number>(30)
  const [analytics, setAnalytics] = useState<AnalyticsTimeseriesResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  const fetchAnalytics = useCallback(
    async (showSpinner: boolean = false) => {
      if (showSpinner) {
        setLoading(true)
      }

      try {
        const response = await apiClient.fetchAnalyticsTimeseries(selectedRange)
        setAnalytics(response)
        setError(null)
      } catch (err) {
        console.error('Failed to load analytics', err)
        setError('Unable to load analytics data. Please try again.')
      } finally {
        if (showSpinner) {
          setLoading(false)
        }
      }
    },
    [selectedRange]
  )

  useEffect(() => {
    fetchAnalytics(true)
  }, [fetchAnalytics])

  const { isPolling, lastUpdated } = usePolling(() => fetchAnalytics(false), {
    interval: 60000,
    enabled: Boolean(analytics),
  })

  const chartData: AnalyticsTimeseriesPoint[] = analytics?.timeseries ?? []

  const lastUpdatedLabel = useMemo(() => {
    if (analytics?.generated_at) {
      const generatedDate = new Date(analytics.generated_at)
      if (!Number.isNaN(generatedDate.getTime())) {
        return generatedDate.toLocaleString()
      }
    }
    if (lastUpdated) {
      return lastUpdated.toLocaleString()
    }
    return null
  }, [analytics, lastUpdated])

  if (loading && !analytics) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-navy-500 border-t-transparent" />
      </div>
    )
  }

  if (error && !analytics) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 px-4">
        <div className="max-w-lg w-full bg-white dark:bg-slate-900 border border-red-200 dark:border-red-800 rounded-2xl p-8 shadow-lg">
          <h2 className="text-xl font-semibold text-red-600 dark:text-red-400 mb-2">
            Something went wrong
          </h2>
          <p className="text-slate-600 dark:text-slate-300">{error}</p>
          <button
            onClick={() => fetchAnalytics(true)}
            className="mt-6 inline-flex items-center px-4 py-2 rounded-lg bg-navy-600 text-white font-medium hover:bg-navy-500"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 p-6">
      <div className="max-w-7xl mx-auto space-y-8">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-navy-600 dark:text-navy-300 font-semibold">
              Growth Overview
            </p>
            <h1 className="text-3xl font-serif font-bold text-slate-900 dark:text-white">
              GATI Analytics Dashboard
            </h1>
            <p className="text-slate-600 dark:text-slate-400 mt-1">
              Track installations, users, events, agents, and MCP activity over time.
            </p>
          </div>

          <div className="flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:gap-4">
            <label className="text-sm text-slate-600 dark:text-slate-300 font-medium">
              Date Range
              <select
                value={selectedRange}
                onChange={(event) => setSelectedRange(Number(event.target.value))}
                className="mt-1 block w-full sm:w-auto rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-navy-500"
              >
                {RANGE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <div className="text-xs text-slate-500 dark:text-slate-400">
              <div className="flex items-center gap-2">
                <span
                  className={`h-2 w-2 rounded-full ${
                    isPolling ? 'bg-green-500 animate-pulse' : 'bg-slate-400'
                  }`}
                />
                Auto-refreshing every 60s
              </div>
              {lastUpdatedLabel && (
                <p className="mt-1">
                  Updated {lastUpdatedLabel}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Summary cards */}
        {analytics?.summary && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4">
            {[
              { label: 'Total Installations', value: analytics.summary.total_installations },
              { label: 'Active (7d)', value: analytics.summary.active_installations },
              { label: 'Authenticated Users', value: analytics.summary.total_users },
              { label: 'Lifetime Events', value: analytics.summary.total_events },
              { label: 'Agents Tracked', value: analytics.summary.total_agents },
              {
                label: 'Growth Rate (MoM)',
                value: analytics.growth_rate_mom
                  ? `${analytics.growth_rate_mom > 0 ? '+' : ''}${analytics.growth_rate_mom.toFixed(1)}%`
                  : 'N/A',
              },
            ].map((card) => (
              <div
                key={card.label}
                className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm"
              >
                <p className="text-xs uppercase tracking-wide text-slate-500 font-semibold">
                  {card.label}
                </p>
                <p className="mt-2 text-3xl font-bold text-navy-600 dark:text-navy-200">
                  {typeof card.value === 'string' ? card.value : card.value.toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        )}

        {/* New Installations Per Week */}
        {chartData.length > 0 && (
          <ChartCard
            title="New Installations Per Week"
            subtitle="Weekly new installation count (last 12 weeks)"
          >
            <ResponsiveContainer width="100%" height={300}>
              <BarChart
                data={(() => {
                  // Group by week
                  const weeklyData: Record<string, number> = {}
                  chartData.forEach((point) => {
                    const date = new Date(point.date)
                    const weekStart = new Date(date)
                    weekStart.setDate(date.getDate() - date.getDay())
                    const weekKey = weekStart.toISOString().split('T')[0]
                    if (!weeklyData[weekKey]) {
                      weeklyData[weekKey] = 0
                    }
                    // Calculate new installations for this day
                    const dayIndex = chartData.findIndex((p) => p.date === point.date)
                    if (dayIndex > 0) {
                      const prevCumulative = chartData[dayIndex - 1].cumulative_installations
                      const newInstalls = point.cumulative_installations - prevCumulative
                      weeklyData[weekKey] += newInstalls
                    }
                  })
                  return Object.entries(weeklyData)
                    .slice(-12)
                    .map(([date, count]) => ({
                      week: new Date(date).toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric',
                      }),
                      new_installations: count,
                    }))
                })()}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#cbd5f5" opacity={0.4} />
                <XAxis dataKey="week" stroke="#94a3b8" tick={{ fontSize: 12 }} />
                <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} allowDecimals={false} />
                <Tooltip contentStyle={tooltipStyles} />
                <Bar dataKey="new_installations" fill="#10b981" />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        )}

        {/* Total Events Over Time (Area Chart) */}
        <ChartCard title="Total Events Tracked Over Time" subtitle="Cumulative events as area chart">
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#cbd5f5" opacity={0.4} />
              <XAxis
                dataKey="date"
                tickFormatter={formatAxisDate}
                stroke="#94a3b8"
                tick={{ fontSize: 12 }}
              />
              <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyles} labelFormatter={formatAxisDate} />
              <Area
                type="monotone"
                dataKey="total_events_per_day"
                stroke="#ec4899"
                fill="#ec4899"
                fillOpacity={0.3}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Charts */}
        <div className="space-y-6">
          <ChartCard title="Daily Active Installations" subtitle="Unique installations seen each day">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#cbd5f5" opacity={0.4} />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatAxisDate}
                  stroke="#94a3b8"
                  tick={{ fontSize: 12 }}
                />
                <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} allowDecimals={false} />
                <Tooltip contentStyle={tooltipStyles} labelFormatter={formatAxisDate} />
                <Line
                  type="monotone"
                  dataKey="daily_active_installations"
                  stroke="#2563eb"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Cumulative Installations" subtitle="Total installations over time">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#cbd5f5" opacity={0.4} />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatAxisDate}
                  stroke="#94a3b8"
                  tick={{ fontSize: 12 }}
                />
                <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} allowDecimals={false} />
                <Tooltip contentStyle={tooltipStyles} labelFormatter={formatAxisDate} />
                <Line
                  type="monotone"
                  dataKey="cumulative_installations"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Total Events Per Day" subtitle="Sum of all reported events each day">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#cbd5f5" opacity={0.4} />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatAxisDate}
                  stroke="#94a3b8"
                  tick={{ fontSize: 12 }}
                />
                <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} allowDecimals={false} />
                <Tooltip contentStyle={tooltipStyles} labelFormatter={formatAxisDate} />
                <Line
                  type="monotone"
                  dataKey="total_events_per_day"
                  stroke="#ec4899"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Active Users Per Day" subtitle="Authenticated users active each day">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#cbd5f5" opacity={0.4} />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatAxisDate}
                  stroke="#94a3b8"
                  tick={{ fontSize: 12 }}
                />
                <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} allowDecimals={false} />
                <Tooltip contentStyle={tooltipStyles} labelFormatter={formatAxisDate} />
                <Line
                  type="monotone"
                  dataKey="active_users"
                  stroke="#a855f7"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Agents Tracked Over Time" subtitle="Total agents monitored each day">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#cbd5f5" opacity={0.4} />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatAxisDate}
                  stroke="#94a3b8"
                  tick={{ fontSize: 12 }}
                />
                <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} allowDecimals={false} />
                <Tooltip contentStyle={tooltipStyles} labelFormatter={formatAxisDate} />
                <Line
                  type="monotone"
                  dataKey="agents_tracked"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="MCP Queries Per Day" subtitle="Total MCP requests recorded each day">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#cbd5f5" opacity={0.4} />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatAxisDate}
                  stroke="#94a3b8"
                  tick={{ fontSize: 12 }}
                />
                <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} allowDecimals={false} />
                <Tooltip contentStyle={tooltipStyles} labelFormatter={formatAxisDate} />
                <Line
                  type="monotone"
                  dataKey="mcp_queries"
                  stroke="#06b6d4"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      </div>
    </div>
  )
}

