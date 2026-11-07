'use client'

import React, { useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, ExternalLink, Search } from 'lucide-react'
import {
  JobQuery,
  JobStatusFilter,
  ROLE_OPTIONS,
  SortField,
  SortOrder,
  WorkplaceType,
  fetchIndustries,
  fetchJobs,
  fetchLocations,
} from '@/lib/api'
import { formatDate, sourceLabel } from '@/lib/format'
import { useDebounced, useLoad } from '@/lib/hooks'
import { Card, EmptyState, ErrorState, VerificationPill } from '@/components/ui'

const PAGE_SIZE = 20

const ROLE_LABELS: Record<(typeof ROLE_OPTIONS)[number], string> = {
  'Product Management Intern': 'Internship',
  'Associate Product Manager': 'APM',
  'Junior Product Manager': 'Junior PM',
  'Graduate Product Manager': 'Graduate PM',
  'Entry-Level Product Manager': 'Entry-level PM',
  'Product Analyst': 'Product Analyst',
  'Product Operations': 'Product Ops',
}

const selectClass =
  'rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none'

function SortHeader({
  field,
  label,
  sortBy,
  sortOrder,
  onSort,
}: {
  field: SortField
  label: string
  sortBy: SortField
  sortOrder: SortOrder
  onSort: (field: SortField) => void
}) {
  const active = field === sortBy
  const Arrow = sortOrder === 'asc' ? ArrowUp : ArrowDown
  return (
    <th scope="col" aria-sort={active ? (sortOrder === 'asc' ? 'ascending' : 'descending') : 'none'} className="px-4 py-3">
      <button onClick={() => onSort(field)} className="flex items-center gap-1 uppercase hover:text-white">
        {label}
        {active && <Arrow className="h-3 w-3" aria-hidden />}
      </button>
    </th>
  )
}

export default function JobsTable({ refreshKey = 0 }: { refreshKey?: number }) {
  const [searchInput, setSearchInput] = useState('')
  const search = useDebounced(searchInput, 300)
  const [roles, setRoles] = useState<string[]>([])
  const [industry, setIndustry] = useState('')
  const [city, setCity] = useState('')
  const [workplace, setWorkplace] = useState<WorkplaceType | ''>('')
  const [withinDays, setWithinDays] = useState('')
  const [status, setStatus] = useState<JobStatusFilter>('active')
  const [recruiterOnly, setRecruiterOnly] = useState(false)
  const [sortBy, setSortBy] = useState<SortField>('date_discovered')
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc')
  const [page, setPage] = useState(1)

  const filtersKey = JSON.stringify([search, roles, industry, city, workplace, withinDays, status, recruiterOnly, sortBy, sortOrder])
  useEffect(() => setPage(1), [filtersKey])

  const query: JobQuery = {
    page,
    page_size: PAGE_SIZE,
    sort_by: sortBy,
    sort_order: sortOrder,
    status,
    search: search || undefined,
    role: roles.length ? roles : undefined,
    industry: industry || undefined,
    city: city || undefined,
    workplace_type: workplace || undefined,
    discovered_within_days: withinDays ? Number(withinDays) : undefined,
    has_recruiter: recruiterOnly ? true : undefined,
  }
  const jobs = useLoad(() => fetchJobs(query), `${filtersKey}|${page}|${refreshKey}`)
  const industries = useLoad(fetchIndustries, `industries|${refreshKey}`)
  const locations = useLoad(fetchLocations, `locations|${refreshKey}`)

  const toggleRole = (role: string) =>
    setRoles((current) => (current.includes(role) ? current.filter((item) => item !== role) : [...current, role]))

  const onSort = (field: SortField) => {
    if (field === sortBy) setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    else {
      setSortBy(field)
      setSortOrder(field === 'title' || field === 'company' || field === 'city' ? 'asc' : 'desc')
    }
  }

  const clearFilters = () => {
    setSearchInput('')
    setRoles([])
    setIndustry('')
    setCity('')
    setWorkplace('')
    setWithinDays('')
    setStatus('active')
    setRecruiterOnly(false)
  }

  const items = jobs.data?.items ?? []
  const total = jobs.data?.total ?? 0
  const totalPages = jobs.data?.total_pages ?? 0
  const filtered = Boolean(
    search || roles.length || industry || city || workplace || withinDays || recruiterOnly || status !== 'active',
  )

  return (
    <Card className="overflow-hidden">
      <div className="space-y-4 border-b border-slate-800 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">Opportunities in India</h2>
            <p className="text-xs text-slate-400" aria-live="polite">
              {jobs.data ? `Showing ${items.length} of ${total.toLocaleString('en-IN')} matching jobs` : 'Loading jobs'}
            </p>
          </div>
          <div className="relative w-full md:w-72">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" aria-hidden />
            <input
              type="search"
              aria-label="Search jobs"
              placeholder="Search title, company, city, skills"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              className="w-full rounded-xl border border-slate-700 bg-slate-950 py-2 pl-9 pr-4 text-sm text-slate-200 placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
            />
          </div>
        </div>

        <div className="flex flex-wrap gap-2" role="group" aria-label="Role type">
          {ROLE_OPTIONS.map((role) => {
            const selected = roles.includes(role)
            return (
              <button
                key={role}
                aria-pressed={selected}
                onClick={() => toggleRole(role)}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                  selected
                    ? 'border-indigo-400 bg-indigo-500/20 text-white'
                    : 'border-slate-700 text-slate-300 hover:border-slate-500'
                }`}
              >
                {ROLE_LABELS[role]}
              </button>
            )
          })}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <select aria-label="Industry" value={industry} onChange={(event) => setIndustry(event.target.value)} className={selectClass}>
            <option value="">All industries</option>
            {industries.data?.map((row) => (
              <option key={row.name} value={row.name}>
                {row.name} ({row.count})
              </option>
            ))}
          </select>
          <select aria-label="City" value={city} onChange={(event) => setCity(event.target.value)} className={selectClass}>
            <option value="">All cities</option>
            {locations.data?.map((row) => (
              <option key={row.name} value={row.name}>
                {row.name} ({row.count})
              </option>
            ))}
          </select>
          <select
            aria-label="Workplace"
            value={workplace}
            onChange={(event) => setWorkplace(event.target.value as WorkplaceType | '')}
            className={selectClass}
          >
            <option value="">Any workplace</option>
            <option value="Remote">Remote</option>
            <option value="Hybrid">Hybrid</option>
            <option value="On-site">On-site</option>
          </select>
          <select aria-label="Discovered" value={withinDays} onChange={(event) => setWithinDays(event.target.value)} className={selectClass}>
            <option value="">Any discovery date</option>
            <option value="1">Last 24 hours</option>
            <option value="7">Last 7 days</option>
            <option value="30">Last 30 days</option>
          </select>
          <select
            aria-label="Status"
            value={status}
            onChange={(event) => setStatus(event.target.value as JobStatusFilter)}
            className={selectClass}
          >
            <option value="active">Active</option>
            <option value="expired">Expired or closed</option>
            <option value="all">All statuses</option>
          </select>
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input type="checkbox" checked={recruiterOnly} onChange={(event) => setRecruiterOnly(event.target.checked)} className="accent-indigo-500" />
            Recruiter contact available
          </label>
        </div>
      </div>

      {jobs.error && (
        <div className="p-4">
          <ErrorState message={jobs.error} onRetry={jobs.reload} />
        </div>
      )}

      {!jobs.error && items.length === 0 && !jobs.loading ? (
        filtered ? (
          <EmptyState title="No jobs match these filters">
            <button onClick={clearFilters} className="font-semibold text-indigo-300 underline">
              Clear all filters
            </button>
          </EmptyState>
        ) : (
          <EmptyState title="No India-eligible jobs yet">
            Nothing has passed validation so far. This count is real: DetectivePM never adds sample listings.
          </EmptyState>
        )
      ) : (
        !jobs.error && (
          <div className="overflow-x-auto" aria-busy={jobs.loading}>
            <table className="w-full border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-950/50 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  <SortHeader field="title" label="Job title" sortBy={sortBy} sortOrder={sortOrder} onSort={onSort} />
                  <SortHeader field="company" label="Company" sortBy={sortBy} sortOrder={sortOrder} onSort={onSort} />
                  <th scope="col" className="px-4 py-3">Industry</th>
                  <th scope="col" className="px-4 py-3">Role type</th>
                  <SortHeader field="city" label="City" sortBy={sortBy} sortOrder={sortOrder} onSort={onSort} />
                  <th scope="col" className="px-4 py-3">Workplace</th>
                  <SortHeader field="date_posted" label="Posted" sortBy={sortBy} sortOrder={sortOrder} onSort={onSort} />
                  <SortHeader field="date_discovered" label="Discovered" sortBy={sortBy} sortOrder={sortOrder} onSort={onSort} />
                  <th scope="col" className="px-4 py-3">Source</th>
                  <th scope="col" className="px-4 py-3">Verification</th>
                  <th scope="col" className="px-4 py-3">Recruiter</th>
                  <th scope="col" className="px-4 py-3"><span className="sr-only">Apply</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {items.map((job) => (
                  <tr key={job.id} className="align-top transition-colors hover:bg-slate-800/30">
                    <td className="min-w-52 px-4 py-3">
                      <Link href={`/jobs/${job.id}`} className="font-medium text-white hover:text-indigo-300">
                        {job.title}
                      </Link>
                      {job.freshness === 'new' && (
                        <span className="ml-2 rounded bg-indigo-500/20 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-indigo-200">New</span>
                      )}
                      {job.provenance === 'demo_seed' && (
                        <span className="ml-2 rounded bg-slate-700 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-slate-200">Demo</span>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-300">{job.company}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-300">{job.industry}</td>
                    <td className="min-w-36 px-4 py-3 text-slate-300">{job.classification ?? 'Unclassified'}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-300">{job.city ?? 'India'}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-300">{job.workplace_type ?? 'Not stated'}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-400">{formatDate(job.date_posted)}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-400">{formatDate(job.date_discovered)}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-400">{sourceLabel(job.source_name)}</td>
                    <td className="px-4 py-3"><VerificationPill status={job.verification_status} /></td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-400">{job.recruiter_available ? 'Available' : 'Not Available'}</td>
                    <td className="px-4 py-3">
                      <a
                        href={job.application_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label={`Apply for ${job.title} at ${job.company}`}
                        className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500"
                      >
                        Apply <ExternalLink className="h-3 w-3" aria-hidden />
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      <div className="flex items-center justify-between border-t border-slate-800 bg-slate-950/30 p-4 text-xs text-slate-400">
        <div>
          Page <span className="font-semibold text-white">{totalPages ? page : 0}</span> of{' '}
          <span className="font-semibold text-white">{totalPages}</span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setPage((value) => Math.max(value - 1, 1))}
            disabled={page <= 1}
            className="flex items-center gap-1 rounded-lg bg-slate-800 px-3 py-1.5 text-slate-200 hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <ChevronLeft className="h-4 w-4" aria-hidden /> Previous
          </button>
          <button
            onClick={() => setPage((value) => value + 1)}
            disabled={page >= totalPages}
            className="flex items-center gap-1 rounded-lg bg-slate-800 px-3 py-1.5 text-slate-200 hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Next <ChevronRight className="h-4 w-4" aria-hidden />
          </button>
        </div>
      </div>
    </Card>
  )
}
