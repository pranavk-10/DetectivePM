import { vi } from 'vitest'
import type { Job, JobMetrics, JobPage, ScraperStatus } from '@/lib/api'

export function job(overrides: Partial<Job> = {}): Job {
  return {
    id: 1,
    title: 'Associate Product Manager',
    company: 'Test Company',
    industry: 'FinTech',
    classification: 'Associate Product Manager',
    relevance_score: 80,
    location: 'Pune, India',
    city: 'Pune',
    state: 'Maharashtra',
    country_code: 'IN',
    workplace_type: 'Hybrid',
    employment_type: 'Full-time',
    date_posted: '2026-11-01T00:00:00Z',
    date_discovered: '2026-11-07T00:00:00Z',
    source_name: 'lever:test',
    verification_status: 'Active',
    is_active: true,
    application_url: 'https://jobs.example.com/1',
    provenance: 'live_source',
    recruiter_available: false,
    freshness: 'new',
    ...overrides,
  }
}

export function page(items: Job[], overrides: Partial<JobPage> = {}): JobPage {
  return { items, total: items.length, page: 1, page_size: 20, total_pages: items.length ? 1 : 0, ...overrides }
}

export const zeroMetrics: JobMetrics = {
  total_jobs: 0,
  active_jobs: 0,
  internships: 0,
  apm_positions: 0,
  junior_graduate_positions: 0,
  verified_recruiter_contacts: 0,
  public_recruiter_contacts: 0,
  new_last_24h: 0,
  new_last_7d: 0,
  by_industry: [],
  by_role: [],
  by_company: [],
  by_city: [],
  by_source: [],
  by_verification: [],
  discovered_over_time: [],
}

export const status: ScraperStatus = {
  scheduler: { state: 'running', last_heartbeat: null, owner: 'worker', next_runs: {}, last_results: {} },
  ingestion_running: false,
  last_successful_ingestion: '2026-11-07T00:00:00Z',
  sources_total: 39,
  sources_healthy: 38,
  sources_failing: 0,
  sources_needing_credentials: 1,
  sources_never_run: 0,
}

type Route = (url: URL, init?: RequestInit) => { status?: number; body: unknown } | undefined

/** Stub fetch by path. An unmatched request fails the test loudly. */
export function stubFetch(route: Route) {
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://localhost')
    const reply = route(url, init)
    if (!reply) throw new Error(`Unexpected request: ${url.pathname}`)
    return new Response(JSON.stringify(reply.body), { status: reply.status ?? 200 })
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

export function jobsRoutes(jobs: JobPage): Route {
  return (url) => {
    if (url.pathname === '/api/jobs') return { body: jobs }
    if (url.pathname === '/api/jobs/industries') return { body: [{ name: 'FinTech', count: 1 }] }
    if (url.pathname === '/api/jobs/locations') return { body: [{ name: 'Pune', count: 1 }] }
    return undefined
  }
}
