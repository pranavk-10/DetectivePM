'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

export function useDebounced<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}

export interface Loadable<T> {
  data: T | null
  error: string | null
  loading: boolean
  reload: () => void
}

/** Load data on mount and when `key` changes. Stale responses are ignored. */
export function useLoad<T>(load: () => Promise<T>, key: string, refreshMs?: number): Loadable<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const latest = useRef(0)
  const loader = useRef(load)
  loader.current = load

  const run = useCallback(async () => {
    const id = ++latest.current
    setLoading(true)
    try {
      const result = await loader.current()
      if (id === latest.current) {
        setData(result)
        setError(null)
      }
    } catch (caught) {
      if (id === latest.current) setError(caught instanceof Error ? caught.message : 'Something went wrong.')
    } finally {
      if (id === latest.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    void run()
    if (!refreshMs) return undefined
    const timer = setInterval(() => void run(), refreshMs)
    return () => clearInterval(timer)
  }, [run, key, refreshMs])

  return { data, error, loading, reload: run }
}
