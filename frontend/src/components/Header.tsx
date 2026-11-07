'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { AlertTriangle, CheckCircle2, Clock3, Download, RefreshCw, Search, XCircle } from 'lucide-react'
import { ApiError, CSV_EXPORT_URL, ScraperStatus, fetchScraperStatus, triggerIngestion } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import { useLoad } from '@/lib/hooks'
import { StatusPill, useAdminAction } from '@/components/ui'

const NAV = [
  { href: '/', label: 'Dashboard' },
  { href: '/sources', label: 'Sources' },
  { href: '/review', label: 'Review' },
]

/** Reported from real scheduler heartbeats and source results, never assumed. */
export function HealthIndicator({ status, failed }: { status: ScraperStatus | null; failed: boolean }) {
  if (failed) return <StatusPill tone="critical" icon={XCircle} label="API unreachable" />
  if (!status) return <StatusPill tone="neutral" icon={Clock3} label="Checking status" />
  if (status.ingestion_running) return <StatusPill tone="good" icon={RefreshCw} label="Ingestion running" />
  if (status.sources_failing > 0) {
    return <StatusPill tone="serious" icon={AlertTriangle} label={`${status.sources_failing} of ${status.sources_total} sources failing`} />
  }
  if (status.sources_healthy === 0) return <StatusPill tone="neutral" icon={Clock3} label="No source has run yet" />
  return <StatusPill tone="good" icon={CheckCircle2} label={`${status.sources_healthy} of ${status.sources_total} sources healthy`} />
}

const SCHEDULER_LABEL: Record<ScraperStatus['scheduler']['state'], string> = {
  running: 'Scheduler running',
  stopped: 'Scheduler stopped',
  not_started: 'Scheduler not started',
}

export default function Header({ onIngestionStarted }: { onIngestionStarted?: () => void }) {
  const pathname = usePathname()
  const status = useLoad(fetchScraperStatus, 'status', 30_000)
  const { run, dialog, busy } = useAdminAction()
  const [notice, setNotice] = useState<string | null>(null)
  const current = status.data

  const startIngestion = () =>
    run(async () => {
      setNotice(null)
      try {
        const result = await triggerIngestion()
        setNotice(result.message)
        status.reload()
        onIngestionStarted?.()
      } catch (caught) {
        if (caught instanceof ApiError && caught.status === 401) throw caught
        setNotice(caught instanceof Error ? caught.message : 'Could not start ingestion.')
      }
    })

  return (
    <header className="flex flex-col gap-4 border-b border-slate-800/80 pb-6 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex items-start gap-4">
        <div className="rounded-2xl bg-gradient-to-tr from-indigo-600 to-purple-600 p-3.5 text-white shadow-xl shadow-indigo-500/20">
          <Search className="h-7 w-7" aria-hidden />
        </div>
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <Link href="/" className="text-2xl font-extrabold tracking-tight text-white sm:text-3xl">
              DetectivePM
            </Link>
            <span className="rounded-full border border-orange-400/30 bg-orange-400/10 px-3 py-1 text-xs font-bold tracking-wide text-orange-100">
              INDIA ONLY 🇮🇳
            </span>
            <HealthIndicator status={current} failed={Boolean(status.error) && !current} />
          </div>
          <p className="mt-1 text-sm text-slate-400">
            Last successful ingestion: <span className="text-slate-200">{formatDateTime(current?.last_successful_ingestion)}</span>
            {current && <span className="ml-2 text-slate-500">· {SCHEDULER_LABEL[current.scheduler.state]}</span>}
          </p>
          <nav className="mt-3 flex gap-4 text-sm" aria-label="Main">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={pathname === item.href ? 'page' : undefined}
                className={pathname === item.href ? 'font-semibold text-white' : 'text-slate-400 hover:text-white'}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {notice && (
          <p role="status" className="max-w-xs text-xs text-slate-300">
            {notice}
          </p>
        )}
        <a
          href={CSV_EXPORT_URL}
          className="flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-900 px-4 py-2.5 text-sm font-semibold text-slate-200 transition-all hover:bg-slate-800 hover:text-white"
        >
          <Download className="h-4 w-4 text-indigo-400" aria-hidden />
          Export CSV
        </a>
        <button
          onClick={startIngestion}
          disabled={busy || current?.ingestion_running}
          className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-600/25 transition-all hover:from-indigo-500 hover:to-purple-500 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${busy || current?.ingestion_running ? 'animate-spin' : ''}`} aria-hidden />
          Refresh jobs
        </button>
      </div>
      {dialog}
    </header>
  )
}
