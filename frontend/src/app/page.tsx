'use client'

import React, { useState } from 'react'
import Charts from '@/components/Charts'
import Header from '@/components/Header'
import JobsTable from '@/components/JobsTable'
import MetricsCards from '@/components/MetricsCards'
import PageShell from '@/components/PageShell'
import { ErrorState } from '@/components/ui'
import { fetchMetrics } from '@/lib/api'
import { useLoad } from '@/lib/hooks'

export default function DashboardPage() {
  const [refreshKey, setRefreshKey] = useState(0)
  const metrics = useLoad(fetchMetrics, `metrics|${refreshKey}`, 30_000)

  return (
    <PageShell>
      <Header onIngestionStarted={() => setRefreshKey((value) => value + 1)} />
      {metrics.error && !metrics.data && <ErrorState message={metrics.error} onRetry={metrics.reload} />}
      <MetricsCards metrics={metrics.data} loading={metrics.loading} />
      {metrics.data && <Charts metrics={metrics.data} />}
      <JobsTable refreshKey={refreshKey} />
    </PageShell>
  )
}
