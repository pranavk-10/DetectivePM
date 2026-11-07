/**
 * DetectivePM - Frontend TypeScript API Client.
 */

const API_BASE = '/api'

export interface PostItem {
  post_id: string
  timestamp: string
  name: string
  account_id: string
  post_content: string
  role_type: 'Intern' | 'Full-time'
  genre: 'SaaS' | 'B2C' | 'FinTech' | 'EdTech' | 'HealthTech' | 'General/Other'
  contacts_present: string
}

export interface PostsResponse {
  items: PostItem[]
  total: number
  page: number
  page_size: number
}

export interface SchedulerStatus {
  last_run: string | null
  next_run: string | null
  is_running: boolean
}

export interface StatsResponse {
  total_posts: number
  intern_count: number
  fulltime_count: number
  genre_breakdown: Record<string, number>
  last_scrape_time: string | null
  scheduler: SchedulerStatus
}

export async function fetchStats(): Promise<StatsResponse> {
  const res = await fetch(`${API_BASE}/stats`, { cache: 'no-store' })
  if (!res.ok) {
    throw new Error('Failed to fetch dashboard stats')
  }
  return res.json()
}

export async function fetchPosts(params: {
  page?: number
  page_size?: number
  role_type?: string
  genre?: string
  search?: string
}): Promise<PostsResponse> {
  const searchParams = new URLSearchParams()
  if (params.page) searchParams.set('page', params.page.toString())
  if (params.page_size) searchParams.set('page_size', params.page_size.toString())
  if (params.role_type) searchParams.set('role_type', params.role_type)
  if (params.genre) searchParams.set('genre', params.genre)
  if (params.search) searchParams.set('search', params.search)

  const res = await fetch(`${API_BASE}/posts?${searchParams.toString()}`, { cache: 'no-store' })
  if (!res.ok) {
    throw new Error('Failed to fetch posts')
  }
  return res.json()
}

export async function triggerScrape(): Promise<{ status: string; message: string; new_posts: number }> {
  const res = await fetch(`${API_BASE}/trigger-scrape`, { method: 'POST' })
  if (!res.ok) {
    throw new Error('Failed to trigger manual scrape')
  }
  return res.json()
}

export async function syncGSheets(spreadsheetId: string): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE}/sync-gsheets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ spreadsheet_id: spreadsheetId }),
  })
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Failed to sync Google Sheets' }))
    throw new Error(errData.detail || 'Failed to sync Google Sheets')
  }
  return res.json()
}

export function getExportUrl(): string {
  return `${API_BASE}/export-csv`
}
