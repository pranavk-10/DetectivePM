'use client'

import React, { useState } from 'react'
import { Play } from 'lucide-react'
import Header from '@/components/Header'
import PageShell from '@/components/PageShell'
import { Card, EmptyState, ErrorState, HealthPill, Skeleton, useAdminAction } from '@/components/ui'
import { SourceInfo, fetchSources, setSourceEnabled, triggerIngestion } from '@/lib/api'
import { formatDateTime, sourceLabel } from '@/lib/format'
import { useLoad } from '@/lib/hooks'

const HEALTH_ORDER: Record<SourceInfo['health'], number> = {
  failing: 0,
  needs_credentials: 1,
  never_run: 2,
  healthy: 3,
  manual: 4,
  disabled: 5,
}

export default function SourcesPage() {
  const sources = useLoad(fetchSources, 'sources', 30_000)
  const { run, dialog, busy } = useAdminAction()
  const [notice, setNotice] = useState<string | null>(null)
  const rows = [...(sources.data ?? [])].sort(
    (a, b) => HEALTH_ORDER[a.health] - HEALTH_ORDER[b.health] || a.source_name.localeCompare(b.source_name),
  )

  const runSource = (source: SourceInfo) =>
    run(async () => {
      const result = await triggerIngestion(source.id)
      setNotice(`${sourceLabel(source.source_name)}: ${result.message}`)
      sources.reload()
    })

  const toggle = (source: SourceInfo) =>
    run(async () => {
      await setSourceEnabled(source.id, !source.enabled)
      sources.reload()
    })

  return (
    <PageShell>
      <Header />
      <div>
        <h1 className="text-xl font-bold text-white">Source monitoring</h1>
        <p className="text-sm text-slate-400">Health comes from each source&apos;s last real run.</p>
        {notice && (
          <p role="status" className="mt-2 text-sm text-slate-300">
            {notice}
          </p>
        )}
      </div>
      {sources.error && <ErrorState message={sources.error} onRetry={sources.reload} />}
      {!sources.data && sources.loading && <Skeleton className="h-64" />}
      {sources.data && rows.length === 0 && (
        <Card>
          <EmptyState title="No sources are registered">Run the registry sync on the backend.</EmptyState>
        </Card>
      )}
      {rows.length > 0 && (
        <Card className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-950/50 text-xs font-semibold uppercase tracking-wider text-slate-400">
                <th scope="col" className="px-4 py-3">Source</th>
                <th scope="col" className="px-4 py-3">Type</th>
                <th scope="col" className="px-4 py-3">Health</th>
                <th scope="col" className="px-4 py-3">Last success</th>
                <th scope="col" className="px-4 py-3">Last failure</th>
                <th scope="col" className="px-4 py-3">Retrieved</th>
                <th scope="col" className="px-4 py-3">Inserted</th>
                <th scope="col" className="px-4 py-3">Current error</th>
                <th scope="col" className="px-4 py-3">Controls</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {rows.map((source) => (
                <tr key={source.id} className="align-top">
                  <td className="whitespace-nowrap px-4 py-3 font-medium text-white">{sourceLabel(source.source_name)}</td>
                  <td className="px-4 py-3 text-slate-400">{source.source_type}</td>
                  <td className="px-4 py-3"><HealthPill health={source.health} /></td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-400">{formatDateTime(source.last_successful_run)}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-400">{formatDateTime(source.last_failure_at)}</td>
                  <td className="px-4 py-3 text-slate-300">{source.jobs_discovered}</td>
                  <td className="px-4 py-3 text-slate-300">{source.jobs_inserted}</td>
                  <td className="max-w-xs px-4 py-3 text-xs text-slate-400">{source.error_message ?? 'None'}</td>
                  <td className="whitespace-nowrap px-4 py-3">
                    {source.source_type !== 'manual' && (
                      <div className="flex gap-2">
                        <button
                          onClick={() => runSource(source)}
                          disabled={busy || !source.enabled}
                          aria-label={`Run ${source.source_name}`}
                          className="inline-flex items-center gap-1 rounded-lg bg-slate-800 px-2.5 py-1 text-xs text-slate-200 hover:bg-slate-700 disabled:opacity-40"
                        >
                          <Play className="h-3 w-3" aria-hidden /> Run
                        </button>
                        <button
                          onClick={() => toggle(source)}
                          disabled={busy}
                          className="rounded-lg bg-slate-800 px-2.5 py-1 text-xs text-slate-200 hover:bg-slate-700 disabled:opacity-40"
                        >
                          {source.enabled ? 'Disable' : 'Enable'}
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      {dialog}
    </PageShell>
  )
}
