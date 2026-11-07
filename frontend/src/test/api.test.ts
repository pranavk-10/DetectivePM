import { describe, expect, it } from 'vitest'
import { ApiError, buildJobQuery, fetchJobs, fetchMetrics, getAdminKey, setAdminKey, triggerIngestion } from '@/lib/api'
import { page, stubFetch } from './fixtures'

const base = { page: 1, page_size: 20, sort_by: 'date_discovered', sort_order: 'desc', status: 'active' } as const

describe('buildJobQuery', () => {
  it('omits filters that are not set, so "All" is never sent', () => {
    const query = buildJobQuery({ ...base, search: '   ', role: undefined, industry: undefined })
    expect(query).toBe('page=1&page_size=20&sort_by=date_discovered&sort_order=desc&status=active')
  })

  it('sends every selected role', () => {
    const params = new URLSearchParams(buildJobQuery({ ...base, role: ['Product Analyst', 'Product Operations'] }))
    expect(params.getAll('role')).toEqual(['Product Analyst', 'Product Operations'])
  })

  it('never sends a country filter', () => {
    expect(buildJobQuery({ ...base, city: 'Pune' })).not.toContain('country')
  })

  it('keeps has_recruiter=false distinct from unset', () => {
    expect(buildJobQuery({ ...base, has_recruiter: false })).toContain('has_recruiter=false')
  })
})

describe('request errors', () => {
  it('uses same-origin /api paths', async () => {
    const mock = stubFetch(() => ({ body: page([]) }))
    await fetchJobs(base)
    expect(String(mock.mock.calls[0][0])).toMatch(/^\/api\/jobs\?/)
  })

  it('surfaces the structured backend message', async () => {
    stubFetch(() => ({ status: 429, body: { error: { code: 'rate_limited', message: 'Try later', details: null } } }))
    await expect(fetchMetrics()).rejects.toMatchObject({ status: 429, code: 'rate_limited', message: 'Try later' })
  })

  it('explains a non-JSON outage', async () => {
    const original = globalThis.fetch
    globalThis.fetch = async () => new Response('<html>bad gateway</html>', { status: 502 })
    await expect(fetchMetrics()).rejects.toThrow('server is unavailable')
    globalThis.fetch = original
  })

  it('reports a network failure as ApiError', async () => {
    const original = globalThis.fetch
    globalThis.fetch = async () => {
      throw new TypeError('failed')
    }
    await expect(fetchMetrics()).rejects.toBeInstanceOf(ApiError)
    globalThis.fetch = original
  })
})

describe('admin key', () => {
  it('lives only in session storage and is sent as a header', async () => {
    setAdminKey('secret')
    expect(getAdminKey()).toBe('secret')
    expect(window.localStorage.length).toBe(0)
    const mock = stubFetch(() => ({ status: 202, body: { status: 'accepted', message: 'Ingestion started' } }))
    await triggerIngestion()
    const init = mock.mock.calls[0][1] as RequestInit
    expect((init.headers as Record<string, string>)['X-Admin-Key']).toBe('secret')
  })
})
