'use client'

import React from 'react'
import Link from 'next/link'
import { ArrowLeft, ExternalLink } from 'lucide-react'
import Header from '@/components/Header'
import PageShell from '@/components/PageShell'
import { Card, ErrorState, Skeleton, VerificationPill } from '@/components/ui'
import { Recruiter, fetchJob } from '@/lib/api'
import { formatDate, formatDateTime, formatSalary, sourceLabel } from '@/lib/format'
import { useLoad } from '@/lib/hooks'

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-200">{children}</dd>
    </div>
  )
}

function TextBlock({ title, text }: { title: string; text: string | null }) {
  if (!text) return null
  return (
    <Card className="p-6">
      <h2 className="mb-3 font-semibold text-white">{title}</h2>
      <p className="whitespace-pre-line text-sm leading-relaxed text-slate-300">{text}</p>
    </Card>
  )
}

function RecruiterCard({ contact }: { contact: Recruiter }) {
  return (
    <li className="rounded-xl border border-slate-800 p-3 text-sm">
      <p className="font-medium text-white">{contact.recruiter_name ?? 'Recruiting contact'}</p>
      {contact.designation && <p className="text-slate-400">{contact.designation}</p>}
      {contact.email && <p className="text-slate-200">{contact.email}</p>}
      {contact.phone && <p className="text-slate-200">{contact.phone}</p>}
      {contact.public_profile_url && (
        <a href={contact.public_profile_url} target="_blank" rel="noopener noreferrer" className="text-indigo-300 underline">
          Public profile
        </a>
      )}
      <p className="mt-1 text-xs text-slate-500">
        {contact.verification_status} ·{' '}
        <a href={contact.source_url} target="_blank" rel="noopener noreferrer" className="underline">
          source
        </a>
      </p>
    </li>
  )
}

export default function JobDetailPage({ params }: { params: { id: string } }) {
  const id = Number(params.id)
  const job = useLoad(() => fetchJob(id), `job|${id}`)
  const data = job.data

  return (
    <PageShell>
      <Header />
      <Link href="/" className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-white">
        <ArrowLeft className="h-4 w-4" aria-hidden /> All jobs
      </Link>
      {job.error && <ErrorState message={job.error} onRetry={job.reload} />}
      {!data && job.loading && <Skeleton className="h-64" />}
      {data && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <Card className="p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h1 className="text-2xl font-bold text-white">{data.title}</h1>
                  <p className="mt-1 text-slate-300">
                    {data.company} · {data.city ?? data.location ?? 'India'}
                  </p>
                  <div className="mt-3">
                    <VerificationPill status={data.verification_status} />
                  </div>
                </div>
                <a
                  href={data.application_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 px-5 py-2.5 text-sm font-semibold text-white hover:from-indigo-500 hover:to-purple-500"
                >
                  Apply on original site <ExternalLink className="h-4 w-4" aria-hidden />
                </a>
              </div>
            </Card>
            <TextBlock title="Responsibilities" text={data.responsibilities} />
            <TextBlock title="Requirements" text={data.requirements} />
            <TextBlock title="Full job description" text={data.description} />
          </div>

          <aside className="space-y-6">
            <Card className="p-6">
              <h2 className="mb-3 font-semibold text-white">Details</h2>
              <dl className="space-y-3">
                <Fact label="Role">{data.classification ?? 'Unclassified'}</Fact>
                <Fact label="Industry">{data.industry}</Fact>
                <Fact label="Location">
                  {[data.city, data.state, data.country_name].filter(Boolean).join(', ') || data.location}
                </Fact>
                <Fact label="Workplace">{data.workplace_type ?? 'Not stated'}</Fact>
                <Fact label="Employment">{data.employment_type ?? 'Not stated'}</Fact>
                <Fact label="Salary">{formatSalary(data.salary_min, data.salary_max, data.salary_currency)}</Fact>
                <Fact label="Posted">{formatDate(data.date_posted)}</Fact>
                <Fact label="Discovered">{formatDate(data.date_discovered)}</Fact>
                <Fact label="Last verified">{formatDateTime(data.last_verified_at)}</Fact>
                <Fact label="Source">
                  {data.sources.length ? data.sources.map(sourceLabel).join(', ') : sourceLabel(data.source_name)}
                </Fact>
              </dl>
            </Card>

            {data.skills.length > 0 && (
              <Card className="p-6">
                <h2 className="mb-3 font-semibold text-white">Skills mentioned</h2>
                <ul className="flex flex-wrap gap-2">
                  {data.skills.map((skill) => (
                    <li key={skill} className="rounded-md border border-slate-700 bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
                      {skill}
                    </li>
                  ))}
                </ul>
              </Card>
            )}

            <Card className="p-6">
              <h2 className="mb-3 font-semibold text-white">Recruiter</h2>
              {data.recruiters.length ? (
                <ul className="space-y-3">
                  {data.recruiters.map((contact) => (
                    <RecruiterCard key={contact.id} contact={contact} />
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-400">Not Available</p>
              )}
            </Card>

            <Card className="p-6">
              <h2 className="mb-3 font-semibold text-white">Why this is listed</h2>
              <dl className="space-y-3">
                <Fact label="India eligibility">{data.location_evidence ?? 'Not recorded'}</Fact>
                <Fact label={`Role score: ${data.relevance_score}/100`}>{data.classification_reason ?? 'Not recorded'}</Fact>
                <Fact label="Industry basis">{data.industry_reason ?? 'Not recorded'}</Fact>
                <Fact label="Verification">{data.verification_reason ?? 'Not recorded'}</Fact>
              </dl>
            </Card>
          </aside>
        </div>
      )}
    </PageShell>
  )
}
