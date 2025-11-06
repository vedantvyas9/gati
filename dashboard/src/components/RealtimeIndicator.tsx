interface RealtimeIndicatorProps {
  isActive?: boolean
  lastUpdated?: Date | null
  pollingInterval?: number
}

export default function RealtimeIndicator({
  isActive = false,
  lastUpdated,
  pollingInterval = 5000,
}: RealtimeIndicatorProps) {
  const formatTime = (date: Date | null | undefined) => {
    if (!date) return 'Never'
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffSecs = Math.floor(diffMs / 1000)

    if (diffSecs < 60) return 'Just now'
    if (diffSecs < 120) return '1 minute ago'
    const diffMins = Math.floor(diffSecs / 60)
    if (diffMins < 60) return `${diffMins} minutes ago`

    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours} hours ago`

    return date.toLocaleString()
  }

  return (
    <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
      <div className="relative flex h-2 w-2">
        {isActive && (
          <>
            <span className="animate-pulse absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
            <span className="absolute inline-flex rounded-full h-2 w-2 bg-green-500"></span>
          </>
        )}
        {!isActive && (
          <span className="absolute inline-flex rounded-full h-2 w-2 bg-gray-400 dark:bg-gray-600"></span>
        )}
      </div>
      <span className="text-xs">
        {isActive ? 'Live' : 'Paused'} • Updated {formatTime(lastUpdated)}
      </span>
    </div>
  )
}
