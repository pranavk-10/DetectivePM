'use client'

import React, { useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  CircleSlash,
  Clock3,
  HelpCircle,
  KeyRound,
  LucideIcon,
  RefreshCw,
  WifiOff,
  XCircle,
} from 'lucide-react'
import { ApiError, getAdminKey, setAdminKey } from '@/lib/api'

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-center justify-between gap-4 rounded-2xl border border-rose-500/20 bg-rose-500/10 p-4 text-sm text-rose-200">
      <span className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden />
        {message}
      </span>
      {onRetry && (
        <button onClick={onRetry} className="shrink-0 text-xs font-semibold underline hover:text-white">
          Try again
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="px-6 py-14 text-center">
      <p className="font-semibold text-slate-200">{title}</p>
      {children && <p className="mx-auto mt-1 max-w-lg text-sm text-slate-400">{children}</p>}
    </div>
  )
}

export function Skeleton({ className = 'h-32' }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded-2xl border border-slate-800 bg-slate-900/50 ${className}`} />
}

export function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-slate-800 bg-slate-900/90 shadow-xl backdrop-blur-sm ${className}`}>
      {children}
    </section>
  )
}

type Tone = 'good' | 'warning' | 'serious' | 'critical' | 'neutral'

const TONES: Record<Tone, string> = {
  good: 'border-[#0ca30c]/40 bg-[#0ca30c]/10 text-slate-100',
  warning: 'border-[#fab219]/40 bg-[#fab219]/10 text-slate-100',
  serious: 'border-[#ec835a]/40 bg-[#ec835a]/10 text-slate-100',
  critical: 'border-[#d03b3b]/50 bg-[#d03b3b]/15 text-slate-100',
  neutral: 'border-slate-700 bg-slate-800 text-slate-300',
}
const ICON_COLOURS: Record<Tone, string> = {
  good: 'text-[#0ca30c]',
  warning: 'text-[#fab219]',
  serious: 'text-[#ec835a]',
  critical: 'text-[#d03b3b]',
  neutral: 'text-slate-400',
}

/** Status always pairs colour with an icon and a word, so colour never carries it alone. */
export function StatusPill({ tone, icon: Icon, label }: { tone: Tone; icon: LucideIcon; label: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONES[tone]}`}>
      <Icon className={`h-3.5 w-3.5 ${ICON_COLOURS[tone]}`} aria-hidden />
      {label}
    </span>
  )
}

const VERIFICATION: Record<string, { tone: Tone; icon: LucideIcon }> = {
  Active: { tone: 'good', icon: CheckCircle2 },
  Expired: { tone: 'neutral', icon: Clock3 },
  Closed: { tone: 'neutral', icon: CircleSlash },
  Unreachable: { tone: 'serious', icon: WifiOff },
  'Requires Manual Review': { tone: 'warning', icon: HelpCircle },
}

export function VerificationPill({ status }: { status: string }) {
  const style = VERIFICATION[status] ?? { tone: 'neutral' as Tone, icon: HelpCircle }
  return <StatusPill tone={style.tone} icon={style.icon} label={status} />
}

const HEALTH: Record<string, { tone: Tone; icon: LucideIcon; label: string }> = {
  healthy: { tone: 'good', icon: CheckCircle2, label: 'Healthy' },
  failing: { tone: 'critical', icon: XCircle, label: 'Failing' },
  needs_credentials: { tone: 'warning', icon: KeyRound, label: 'Needs credentials' },
  never_run: { tone: 'neutral', icon: Clock3, label: 'Never run' },
  disabled: { tone: 'neutral', icon: CircleSlash, label: 'Disabled' },
  manual: { tone: 'neutral', icon: HelpCircle, label: 'Manual input' },
}

export function HealthPill({ health }: { health: string }) {
  const style = HEALTH[health] ?? HEALTH.never_run
  return <StatusPill tone={style.tone} icon={style.icon} label={style.label} />
}

/** Runs an admin action, asking for the key first if this tab does not have one. */
export function useAdminAction() {
  const [pending, setPending] = useState<(() => Promise<void>) | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const execute = async (action: () => Promise<void>) => {
    setBusy(true)
    setError(null)
    try {
      await action()
      setPending(null)
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) {
        setAdminKey(null)
        setPending(() => action)
      }
      setError(caught instanceof Error ? caught.message : 'That action failed.')
    } finally {
      setBusy(false)
    }
  }

  const run = (action: () => Promise<void>) => {
    if (getAdminKey()) void execute(action)
    else setPending(() => action)
  }

  const dialog = pending ? (
    <AdminKeyDialog
      busy={busy}
      error={error}
      onCancel={() => {
        setPending(null)
        setError(null)
      }}
      onSubmit={(key) => {
        setAdminKey(key)
        void execute(pending)
      }}
    />
  ) : null

  return { run, dialog, busy, error, clearError: () => setError(null) }
}

function AdminKeyDialog({
  busy,
  error,
  onCancel,
  onSubmit,
}: {
  busy: boolean
  error: string | null
  onCancel: () => void
  onSubmit: (key: string) => void
}) {
  const [key, setKey] = useState('')
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
      <form
        role="dialog"
        aria-label="Administrator key"
        onSubmit={(event) => {
          event.preventDefault()
          if (key.trim()) onSubmit(key.trim())
        }}
        className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl"
      >
        <h2 className="text-lg font-bold text-white">Administrator key</h2>
        <p className="mt-1 text-sm text-slate-400">This action is restricted. The key stays in this browser tab only.</p>
        <label className="mt-4 block text-xs font-medium text-slate-400" htmlFor="admin-key">
          Key
        </label>
        <input
          id="admin-key"
          type="password"
          autoFocus
          autoComplete="off"
          value={key}
          onChange={(event) => setKey(event.target.value)}
          className="mt-1.5 w-full rounded-xl border border-slate-800 bg-slate-950 px-4 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        {error && (
          <p role="alert" className="mt-2 text-xs text-rose-300">
            {error}
          </p>
        )}
        <div className="mt-5 flex justify-end gap-3">
          <button type="button" onClick={onCancel} className="rounded-xl bg-slate-800 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-slate-700">
            Cancel
          </button>
          <button type="submit" disabled={busy} className="flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50">
            {busy && <RefreshCw className="h-4 w-4 animate-spin" aria-hidden />}
            Continue
          </button>
        </div>
      </form>
    </div>
  )
}
