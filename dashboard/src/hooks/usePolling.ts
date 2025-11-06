import { useEffect, useRef, useState } from 'react'

interface UsePollingOptions {
  interval?: number
  enabled?: boolean
  onPoll?: () => void | Promise<void>
  onError?: (error: Error) => void
}

/**
 * Custom hook for polling data at regular intervals
 * @param callback Function to call on each poll interval
 * @param options Configuration options
 */
export function usePolling(
  callback: () => void | Promise<void>,
  options: UsePollingOptions = {}
) {
  const { interval = 5000, enabled = true, onPoll, onError } = options
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [isPolling, setIsPolling] = useState(false)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  useEffect(() => {
    if (!enabled) {
      return
    }

    const poll = async () => {
      try {
        setIsPolling(true)
        await callback()
        onPoll?.()
        setLastUpdated(new Date())
      } catch (error) {
        const err = error instanceof Error ? error : new Error(String(error))
        onError?.(err)
      } finally {
        setIsPolling(false)
        // Schedule next poll
        timeoutRef.current = setTimeout(poll, interval)
      }
    }

    // Initial poll after a short delay
    timeoutRef.current = setTimeout(poll, 100)

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [callback, interval, enabled, onPoll, onError])

  return {
    isPolling,
    lastUpdated,
  }
}

/**
 * Custom hook for managing multiple polling intervals
 * Useful when you need to poll different data at different rates
 */
export function useMultiplePolling(
  callbacks: Array<{
    fn: () => void | Promise<void>
    interval?: number
    enabled?: boolean
  }>,
  globalOptions?: UsePollingOptions
) {
  const pollings = callbacks.map((cb) =>
    usePolling(cb.fn, {
      interval: cb.interval,
      enabled: cb.enabled,
      ...globalOptions,
    })
  )

  return {
    isAnyPolling: pollings.some((p) => p.isPolling),
    lastUpdated: pollings
      .map((p) => p.lastUpdated)
      .filter((t) => t !== null)
      .sort()
      .pop() as Date | null,
  }
}
