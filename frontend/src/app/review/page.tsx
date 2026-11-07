'use client'

import React, { useState } from 'react'
import { ExternalLink } from 'lucide-react'
import Header from '@/components/Header'
import PageShell from '@/components/PageShell'
import { Card, EmptyState, ErrorState, useAdminAction } from '@/components/ui'
import { ROLE_OPTIONS, ReviewItem, ReviewPage, fetchReviewQueue, reviewJob } from '@/lib/api'
import { formatDate, sourceLabel } from '@/lib/format'

function ReviewRow({
  item,
  onDecide,
}: {
  item: ReviewItem
  onDecide: (decision: 'approve' | 'reject', note: string, role: string) => void
}) {
  const [note, setNote] = useState('')
  const [role, setRole] = useState<string>(ROLE_OPTIONS[4])
  return (
    <li className="space-y-3 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-medium text-white">{item.title}</p>
          <p className="text-sm text-slate-400">
            {item.company} · {item.location ?? 'No location'} · {sourceLabel(item.source_name)} · found {formatDate(item.date_discovered)}
          </p>
        </div>
        <a href={item.application_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm text-indigo-300 underline">
          Open posting <ExternalLink className="h-3 w-3" aria-hidden />
        </a>
      </div>
      <p className="text-sm text-slate-300">{item.review_reason}</p>
      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label={`Role for ${item.title}`}
          value={role}
          onChange={(event) => setRole(event.target.value)}
          className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200"
        >
          {ROLE_OPTIONS.map((option) => (
            <option key={option}>{option}</option>
          ))}
        </select>
        <input
          aria-label={`Evidence for ${item.title}`}
          placeholder="Evidence for your decision"
          value={note}
          onChange={(event) => setNote(event.target.value)}
          className="min-w-64 flex-1 rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
        />
        <button
          disabled={!note.trim()}
          onClick={() => onDecide('approve', note, role)}
          className="rounded-xl bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-40"
        >
          Approve
        </button>
        <button
          onClick={() => onDecide('reject', note, role)}
          className="rounded-xl bg-slate-800 px-3 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-700"
        >
          Reject
        </button>
      </div>
    </li>
  )
}

export default function ReviewQueuePage() {
  const [queue, setQueue] = useState<ReviewPage | null>(null)
  const { run, dialog, error } = useAdminAction()

  const load = () =>
    run(async () => {
      setQueue(await fetchReviewQueue(1))
    })

  const decide = (id: number, decision: 'approve' | 'reject', note: string, role: string) =>
    run(async () => {
      await reviewJob(id, decision, note, decision === 'approve' ? role : undefined)
      setQueue(await fetchReviewQueue(1))
    })

  return (
    <PageShell>
      <Header />
      <div>
        <h1 className="text-xl font-bold text-white">Manual review</h1>
        <p className="text-sm text-slate-400">
          Jobs with unconfirmed India eligibility or an uncertain role wait here and stay out of public listings.
        </p>
      </div>
      {error && !dialog && <ErrorState message={error} />}
      {!queue ? (
        <button onClick={load} className="rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-500">
          Open review queue
        </button>
      ) : (
        <Card>
          <p className="border-b border-slate-800 p-5 text-sm text-slate-300">{queue.total} jobs waiting</p>
          {queue.items.length === 0 ? (
            <EmptyState title="Nothing is waiting for review" />
          ) : (
            <ul className="divide-y divide-slate-800/60">
              {queue.items.map((item) => (
                <ReviewRow key={item.id} item={item} onDecide={(decision, note, role) => decide(item.id, decision, note, role)} />
              ))}
            </ul>
          )}
        </Card>
      )}
      {dialog}
    </PageShell>
  )
}
