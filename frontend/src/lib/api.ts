/**
 * Typed API client. All types come from src/lib/api-types.ts, generated from the
 * backend's OpenAPI document (`npm run types`), so the contract cannot drift.
 * Requests are same-origin; next.config.js forwards /api to the backend.
 */
import type { components } from './api-types'

type Schemas = components['schemas']

export type Job = Schemas['JobListItem']
export type JobDetail = Schemas['JobDetail']
export type JobPage = Schemas['JobPage']
export type JobMetrics = Schemas['JobMetrics']
export type CountBucket = Schemas['CountBucket']
export type DateBucket = Schemas['DateBucket']
export type Recruiter = Schemas['RecruiterOut']
export type ScraperStatus = Schemas['ScraperStatus']
export type SourceInfo = Schemas['SourceOut']
export type ReviewItem = Schemas['ReviewItem']
export type ReviewPage = Schemas['ReviewPage']
export type ApiErrorBody = Schemas['ErrorResponse']

export const ROLE_OPTIONS = [
  'Product Management Intern',
  'Associate Product Manager',
  'Junior Product Manager',
  'Graduate Product Manager',
  'Entry-Level Product Manager',
  'Product Analyst',
  'Product Operations',
] as const

export type SortField = 'date_discovered' | 'date_posted' | 'title' | 'company' | 'city' | 'relevance_score'
export type SortOrder = 'asc' | 'desc'
export type WorkplaceType = 'Remote' | 'Hybrid' | 'On-site'
export type JobStatusFilter = 'active' | 'expired' | 'all'

export interface JobQuery {
  page: number
  page_size: number
  sort_by: SortField
  sort_order: SortOrder
  status: JobStatusFilter
  search?: string
  role?: string[]
  industry?: string
  city?: string
  workplace_type?: WorkplaceType
  discovered_within_days?: number
  has_recruiter?: boolean
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly code: string = 'error',
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, { cache: 'no-store', ...init })
  } catch {
    throw new ApiError(0, 'Could not reach the DetectivePM server.', 'network_error')
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorBody | null
    const fallback =
      response.status >= 500
        ? 'The DetectivePM server is unavailable.'
        : `Request failed with status ${response.status}.`
    throw new ApiError(response.status, body?.error?.message ?? fallback, body?.error?.code)
  }
  return (await response.json()) as T
}

export function buildJobQuery(query: JobQuery): string {
  const params = new URLSearchParams({
    page: String(query.page),
    page_size: String(query.page_size),
    sort_by: query.sort_by,
    sort_order: query.sort_order,
    status: query.status,
  })
  const search = query.search?.trim()
  if (search) params.set('search', search)
  query.role?.forEach((role) => params.append('role', role))
  if (query.industry) params.set('industry', query.industry)
  if (query.city) params.set('city', query.city)
  if (query.workplace_type) params.set('workplace_type', query.workplace_type)
  if (query.discovered_within_days) params.set('discovered_within_days', String(query.discovered_within_days))
  if (query.has_recruiter !== undefined) params.set('has_recruiter', String(query.has_recruiter))
  return params.toString()
}

export const fetchJobs = (query: JobQuery) => request<JobPage>(`/api/jobs?${buildJobQuery(query)}`)
export const fetchJob = (id: number) => request<JobDetail>(`/api/jobs/${id}`)
export const fetchMetrics = () => request<JobMetrics>('/api/jobs/metrics')
export const fetchIndustries = () => request<CountBucket[]>('/api/jobs/industries')
export const fetchLocations = () => request<CountBucket[]>('/api/jobs/locations')
export const fetchScraperStatus = () => request<ScraperStatus>('/api/scraper/status')
export const fetchSources = () => request<SourceInfo[]>('/api/sources')

export const CSV_EXPORT_URL = '/api/export/csv'

const ADMIN_KEY = 'detectivepm.adminKey'

export function getAdminKey(): string | null {
  return typeof window === 'undefined' ? null : window.sessionStorage.getItem(ADMIN_KEY)
}

export function setAdminKey(key: string | null): void {
  if (key) window.sessionStorage.setItem(ADMIN_KEY, key)
  else window.sessionStorage.removeItem(ADMIN_KEY)
}

function adminRequest<T>(path: string, method: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method,
    headers: { 'Content-Type': 'application/json', 'X-Admin-Key': getAdminKey() ?? '' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export const triggerIngestion = (sourceId?: number) =>
  adminRequest<Schemas['ScrapeAccepted']>('/api/scraper/run', 'POST', sourceId ? { source_id: sourceId } : {})

export const setSourceEnabled = (id: number, enabled: boolean) =>
  adminRequest<SourceInfo>(`/api/sources/${id}`, 'PATCH', { enabled })

export const fetchReviewQueue = (page: number) =>
  adminRequest<ReviewPage>(`/api/jobs/review-queue?page=${page}&page_size=20`, 'GET')

export const reviewJob = (id: number, decision: 'approve' | 'reject', note: string, classification?: string) =>
  adminRequest<Schemas['JobVerifyResult']>(`/api/jobs/${id}/verify`, 'POST', { decision, note, classification })
