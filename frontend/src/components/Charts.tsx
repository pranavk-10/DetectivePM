'use client'

import React from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { CountBucket, JobMetrics } from '@/lib/api'
import { sourceLabel } from '@/lib/format'
import { Card, EmptyState, VerificationPill } from '@/components/ui'

/* One magnitude per chart, so one hue. The reference blue was checked with the
   palette validator against this dashboard's card surface. */
const BAR = '#3987e5'
const AXIS = '#94a3b8'
const GRID = '#1e293b'
const ROW_HEIGHT = 30

const tooltipStyle = {
  backgroundColor: '#0f172a',
  border: '1px solid #334155',
  borderRadius: '0.75rem',
  color: '#f8fafc',
  fontSize: 12,
}

function ChartCard({ title, children, wide = false }: { title: string; children: React.ReactNode; wide?: boolean }) {
  return (
    <Card className={`p-5 ${wide ? 'lg:col-span-2' : ''}`}>
      <h2 className="mb-3 text-sm font-semibold text-white">{title}</h2>
      {children}
    </Card>
  )
}

function RankedBars({ data, format }: { data: CountBucket[]; format?: (name: string) => string }) {
  if (data.length === 0) return <EmptyState title="No data yet" />
  const rows = data.map((row) => ({ ...row, label: format ? format(row.name) : row.name }))
  return (
    <ResponsiveContainer width="100%" height={rows.length * ROW_HEIGHT + 12}>
      <BarChart data={rows} layout="vertical" margin={{ left: 4, right: 28, top: 4, bottom: 4 }} barCategoryGap={8}>
        <XAxis type="number" hide allowDecimals={false} />
        <YAxis type="category" dataKey="label" width={172} tick={{ fill: AXIS, fontSize: 12 }} axisLine={false} tickLine={false} interval={0} />
        <Tooltip cursor={{ fill: '#1e293b' }} contentStyle={tooltipStyle} formatter={(value) => [String(value), 'Jobs']} />
        <Bar
          dataKey="count"
          fill={BAR}
          radius={[0, 4, 4, 0]}
          maxBarSize={18}
          isAnimationActive={false}
          label={{ position: 'right', fill: '#cbd5e1', fontSize: 12 }}
        />
      </BarChart>
    </ResponsiveContainer>
  )
}

function Timeline({ data }: { data: JobMetrics['discovered_over_time'] }) {
  if (data.length === 0) return <EmptyState title="No data yet" />
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey="date" tick={{ fill: AXIS, fontSize: 12 }} axisLine={{ stroke: GRID }} tickLine={false} />
        <YAxis allowDecimals={false} width={32} tick={{ fill: AXIS, fontSize: 12 }} axisLine={false} tickLine={false} />
        <Tooltip cursor={{ fill: '#1e293b' }} contentStyle={tooltipStyle} formatter={(value) => [String(value), 'Jobs discovered']} />
        <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={32} isAnimationActive={false}>
          {data.map((point) => (
            <Cell key={point.date} fill={BAR} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/** Status is a table of labelled pills: each state needs its word and icon. */
function VerificationList({ data }: { data: CountBucket[] }) {
  if (data.length === 0) return <EmptyState title="No data yet" />
  return (
    <ul className="space-y-2">
      {data.map((row) => (
        <li key={row.name} className="flex items-center justify-between text-sm">
          <VerificationPill status={row.name} />
          <span className="font-semibold text-slate-200">{row.count}</span>
        </li>
      ))}
    </ul>
  )
}

export default function Charts({ metrics }: { metrics: JobMetrics }) {
  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
      <ChartCard title="Jobs discovered over time" wide>
        <Timeline data={metrics.discovered_over_time} />
      </ChartCard>
      <ChartCard title="Jobs by role type">
        <RankedBars data={metrics.by_role} />
      </ChartCard>
      <ChartCard title="Jobs by industry">
        <RankedBars data={metrics.by_industry} />
      </ChartCard>
      <ChartCard title="Jobs by company (top 10)">
        <RankedBars data={metrics.by_company} />
      </ChartCard>
      <ChartCard title="Jobs by city (top 10)">
        <RankedBars data={metrics.by_city} />
      </ChartCard>
      <ChartCard title="Jobs by source (top 10)">
        <RankedBars data={metrics.by_source} format={sourceLabel} />
      </ChartCard>
      <ChartCard title="Verification status">
        <VerificationList data={metrics.by_verification} />
      </ChartCard>
    </div>
  )
}
