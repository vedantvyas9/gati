import { useState, useCallback, useEffect, useMemo } from 'react'
import { apiClient } from '../services/api'
import { usePolling } from '../hooks/usePolling'
import { AnalyticsSummaryCards } from '../types'

type SummaryCardKey =
  | 'total_events'
  | 'total_installations'
  | 'total_mcp_queries'
  | 'total_agents'

const CARD_CONFIG: Array<{ key: SummaryCardKey; label: string }> = [
  { key: 'total_events', label: 'Total Events Tracked' },
  { key: 'total_installations', label: 'Total Installations' },
  { key: 'total_mcp_queries', label: 'Total MCP Queries' },
  { key: 'total_agents', label: 'Total Agents' },
]

const formatNumber = (value?: number) => {
  if (value === undefined || value === null) return '—'
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(1)}K`
  }
  return value.toLocaleString()
}

export default function AnalyticsDashboard() {
  const [summary, setSummary] = useState<AnalyticsSummaryCards | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [generatedAt, setGeneratedAt] = useState<Date | null>(null)

  const fetchSummary = useCallback(
    async (showSpinner: boolean = false) => {
      if (showSpinner) {
        setLoading(true)
      }

      try {
        const response = await apiClient.fetchAnalyticsTimeseries()
        setSummary(response.summary)
        const generated = response.generated_at ? new Date(response.generated_at) : null
        setGeneratedAt(generated && !Number.isNaN(generated.getTime()) ? generated : new Date())
        setError(null)
      } catch (err) {
        console.error('Failed to load telemetry summary', err)
        setError('Unable to load telemetry data. Please try again.')
      } finally {
        if (showSpinner) {
          setLoading(false)
        }
      }
    },
    []
  )

  useEffect(() => {
    fetchSummary(true)
  }, [fetchSummary])

  const { isPolling, lastUpdated } = usePolling(() => fetchSummary(false), {
    interval: 60000,
    enabled: Boolean(summary),
  })

  const updatedLabel = useMemo(() => {
    const reference = generatedAt || lastUpdated
    return reference ? reference.toLocaleString() : null
  }, [generatedAt, lastUpdated])

  if (loading && !summary) {
    return (
      <div className="min-h-[50vh] flex items-center justify-center">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-navy-500 border-t-transparent" />
      </div>
    )
  }

  if (error && !summary) {
    return (
      <div className="min-h-[50vh] flex items-center justify-center px-4">
        <div className="max-w-md w-full bg-white dark:bg-slate-900 border border-red-200 dark:border-red-800 rounded-2xl p-8 shadow-lg">
          <h2 className="text-xl font-semibold text-red-600 dark:text-red-400 mb-2">
            Something went wrong
          </h2>
          <p className="text-slate-600 dark:text-slate-300">{error}</p>
          <button
            onClick={() => fetchSummary(true)}
            className="mt-6 inline-flex items-center px-4 py-2 rounded-lg bg-navy-600 text-white font-medium hover:bg-navy-500"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <section className="space-y-8">
      <div className="space-y-2">
        <p className="text-xs uppercase tracking-wide text-navy-600 dark:text-navy-300 font-semibold">
          Telemetry Overview
        </p>
        <h1 className="text-4xl font-serif font-bold text-slate-900 dark:text-white">
          GATI Install Base
        </h1>
        <p className="text-slate-600 dark:text-slate-400">
          Single pane of glass for installs, events, MCP usage, and agents tracked across the network.
        </p>
      </div>

      {error && summary && (
        <div className="rounded-2xl border border-yellow-200 dark:border-yellow-700 bg-yellow-50 dark:bg-yellow-900/20 p-4 text-sm text-yellow-900 dark:text-yellow-100 flex items-center justify-between gap-4">
          <span>{error}</span>
          <button
            onClick={() => fetchSummary(true)}
            className="px-3 py-1 rounded-lg bg-yellow-100 dark:bg-yellow-800 text-yellow-900 dark:text-yellow-50 text-xs font-semibold"
          >
            Retry
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {CARD_CONFIG.map(({ key, label }) => (
          <div
            key={key}
            className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-sm flex flex-col gap-4"
          >
            <p className="text-xs uppercase tracking-wide text-slate-500 font-semibold">{label}</p>
            <p className="text-4xl font-black text-navy-600 dark:text-navy-200">
              {formatNumber(summary?.[key])}
            </p>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-2 text-sm text-slate-500 dark:text-slate-400">
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${
              isPolling ? 'bg-green-500 animate-pulse' : 'bg-slate-400'
            }`}
          />
          Auto-refreshing every 60 seconds
        </div>
        {updatedLabel && <span>Last updated {updatedLabel}</span>}
      </div>
    </section>
  )
}

