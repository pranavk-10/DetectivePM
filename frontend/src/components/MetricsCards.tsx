'use client'

import React from 'react'
import { Briefcase, CalendarDays, CircleDot, Database, GraduationCap, LucideIcon, Sparkles, UserCheck, Users } from 'lucide-react'
import type { JobMetrics } from '@/lib/api'
import { Skeleton } from '@/components/ui'

interface Metric {
  title: string
  value: number
  note: string
  icon: LucideIcon
}

function toCards(metrics: JobMetrics): Metric[] {
  return [
    { title: 'India-eligible jobs', value: metrics.total_jobs, note: 'Genuine listings on record', icon: Database },
    { title: 'Active opportunities', value: metrics.active_jobs, note: 'Open for applications', icon: CircleDot },
    { title: 'Product internships', value: metrics.internships, note: 'Intern roles', icon: GraduationCap },
    { title: 'APM positions', value: metrics.apm_positions, note: 'Associate product managers', icon: Briefcase },
    { title: 'Junior and graduate PM', value: metrics.junior_graduate_positions, note: 'Junior, graduate, entry level', icon: Users },
    {
      title: 'Verified recruiters',
      value: metrics.verified_recruiter_contacts,
      note: `${metrics.public_recruiter_contacts} more publicly listed`,
      icon: UserCheck,
    },
    { title: 'New in 24 hours', value: metrics.new_last_24h, note: 'First discovered today', icon: Sparkles },
    { title: 'New in 7 days', value: metrics.new_last_7d, note: 'First discovered this week', icon: CalendarDays },
  ]
}

export default function MetricsCards({ metrics, loading }: { metrics: JobMetrics | null; loading: boolean }) {
  if (!metrics) {
    if (!loading) return null
    return (
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {Array.from({ length: 8 }, (_, index) => (
          <Skeleton key={index} className="h-28" />
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {toCards(metrics).map(({ title, value, note, icon: Icon }) => (
        <div key={title} className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 shadow-xl">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium text-slate-400">{title}</span>
            <Icon className="h-4 w-4 shrink-0 text-indigo-400" aria-hidden />
          </div>
          <div data-testid={title} className="mt-2 text-3xl font-extrabold tracking-tight text-white">
            {value.toLocaleString('en-IN')}
          </div>
          <div className="mt-1 text-xs text-slate-500">{note}</div>
        </div>
      ))}
    </div>
  )
}
