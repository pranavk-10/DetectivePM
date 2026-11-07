import React from 'react'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import Header, { HealthIndicator } from '@/components/Header'
import JobsTable from '@/components/JobsTable'
import MetricsCards from '@/components/MetricsCards'
import { job, jobsRoutes, page, status, stubFetch, zeroMetrics } from './fixtures'

const jobCalls = (mock: ReturnType<typeof stubFetch>) =>
  mock.mock.calls
    .map(([input]) => new URL(String(input), 'http://localhost'))
    .filter((url) => url.pathname === '/api/jobs')

describe('MetricsCards', () => {
  it('shows values from the API and honest zeros', () => {
    render(<MetricsCards metrics={{ ...zeroMetrics, total_jobs: 12, public_recruiter_contacts: 3 }} loading={false} />)
    expect(screen.getByTestId('India-eligible jobs')).toHaveTextContent('12')
    expect(screen.getByTestId('Verified recruiters')).toHaveTextContent('0')
    expect(screen.getByText('3 more publicly listed')).toBeInTheDocument()
  })

  it('shows skeletons rather than zeros while loading', () => {
    render(<MetricsCards metrics={null} loading />)
    expect(screen.queryByTestId('India-eligible jobs')).not.toBeInTheDocument()
  })
})

describe('HealthIndicator', () => {
  it('reports healthy sources from real counts', () => {
    render(<HealthIndicator status={status} failed={false} />)
    expect(screen.getByText('38 of 39 sources healthy')).toBeInTheDocument()
  })

  it('reports failures, not a hardcoded success', () => {
    render(<HealthIndicator status={{ ...status, sources_failing: 3 }} failed={false} />)
    expect(screen.getByText('3 of 39 sources failing')).toBeInTheDocument()
  })

  it('reports an unreachable API', () => {
    render(<HealthIndicator status={null} failed />)
    expect(screen.getByText('API unreachable')).toBeInTheDocument()
  })

  it('does not claim health before any source has run', () => {
    render(<HealthIndicator status={{ ...status, sources_healthy: 0 }} failed={false} />)
    expect(screen.getByText('No source has run yet')).toBeInTheDocument()
  })
})

describe('Header', () => {
  it('always shows the India-only marker and has no country selector', async () => {
    stubFetch((url) => (url.pathname === '/api/scraper/status' ? { body: status } : undefined))
    render(<Header />)
    expect(screen.getByText('INDIA ONLY 🇮🇳')).toBeInTheDocument()
    expect(await screen.findByText(/Scheduler running/)).toBeInTheDocument()
    expect(screen.queryByLabelText(/country/i)).not.toBeInTheDocument()
  })

  it('asks for the admin key before running ingestion, and sends it', async () => {
    const mock = stubFetch((url) => {
      if (url.pathname === '/api/scraper/status') return { body: status }
      if (url.pathname === '/api/scraper/run') return { status: 202, body: { status: 'accepted', message: 'Ingestion started' } }
      return undefined
    })
    render(<Header />)
    await userEvent.click(screen.getByRole('button', { name: /Refresh jobs/ }))
    await userEvent.type(screen.getByLabelText('Key'), 'k')
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Ingestion started')
    expect(mock.mock.calls.some(([input]) => String(input) === '/api/scraper/run')).toBe(true)
  })
})

describe('JobsTable', () => {
  it('renders a row with an external apply link', async () => {
    stubFetch(jobsRoutes(page([job()])))
    render(<JobsTable />)
    const row = (await screen.findByRole('link', { name: 'Associate Product Manager' })).closest('tr') as HTMLElement
    expect(within(row).getByText('Pune')).toBeInTheDocument()
    expect(within(row).getByText('Not Available')).toBeInTheDocument()
    const apply = within(row).getByRole('link', { name: /Apply for/ })
    expect(apply).toHaveAttribute('href', 'https://jobs.example.com/1')
    expect(apply).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('links to the job details view', async () => {
    stubFetch(jobsRoutes(page([job({ id: 42 })])))
    render(<JobsTable />)
    expect(await screen.findByRole('link', { name: 'Associate Product Manager' })).toHaveAttribute('href', '/jobs/42')
  })

  it('states an honest empty result', async () => {
    stubFetch(jobsRoutes(page([])))
    render(<JobsTable />)
    expect(await screen.findByText('No India-eligible jobs yet')).toBeInTheDocument()
    expect(screen.getByText(/never adds sample listings/)).toBeInTheDocument()
  })

  it('shows an error with retry, and recovers', async () => {
    let healthy = false
    const routes = jobsRoutes(page([job()]))
    stubFetch((url, init) => {
      if (url.pathname === '/api/jobs' && !healthy) {
        return { status: 503, body: { error: { code: 'service_unavailable', message: 'Database down', details: null } } }
      }
      return routes(url, init)
    })
    render(<JobsTable />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Database down')
    healthy = true
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('link', { name: 'Associate Product Manager' })).toBeInTheDocument()
  })

  it('debounces search into a single backend request', async () => {
    const mock = stubFetch(jobsRoutes(page([job()])))
    render(<JobsTable />)
    await screen.findByRole('link', { name: 'Associate Product Manager' })
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search jobs' }), 'sql')
    await waitFor(() => expect(jobCalls(mock).at(-1)?.searchParams.get('search')).toBe('sql'), { timeout: 2000 })
    const searches = jobCalls(mock).map((url) => url.searchParams.get('search')).filter(Boolean)
    expect(searches).toEqual(['sql'])
  })

  it('sends filters to the backend and omits unset ones', async () => {
    const mock = stubFetch(jobsRoutes(page([job()])))
    render(<JobsTable />)
    await screen.findByRole('link', { name: 'Associate Product Manager' })
    await userEvent.click(screen.getByRole('button', { name: 'Internship' }))
    await waitFor(() => expect(jobCalls(mock).at(-1)?.searchParams.get('role')).toBe('Product Management Intern'))
    await userEvent.selectOptions(screen.getByLabelText('Workplace'), 'Hybrid')
    await waitFor(() => expect(jobCalls(mock).at(-1)?.searchParams.get('workplace_type')).toBe('Hybrid'))
    await userEvent.click(screen.getByLabelText('Recruiter contact available'))
    await waitFor(() => expect(jobCalls(mock).at(-1)?.searchParams.get('has_recruiter')).toBe('true'))
    const last = jobCalls(mock).at(-1)?.searchParams
    expect(last?.has('industry')).toBe(false)
    expect(last?.has('country')).toBe(false)
  })

  it('offers to clear filters when they exclude everything', async () => {
    stubFetch(jobsRoutes(page([])))
    render(<JobsTable />)
    await screen.findByText('No India-eligible jobs yet')
    await userEvent.selectOptions(screen.getByLabelText('Workplace'), 'Remote')
    expect(await screen.findByText('No jobs match these filters')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Clear all filters' }))
    expect(await screen.findByText('No India-eligible jobs yet')).toBeInTheDocument()
  })

  it('paginates from total_pages', async () => {
    const mock = stubFetch(jobsRoutes(page([job()], { total: 45, total_pages: 3 })))
    render(<JobsTable />)
    await screen.findByRole('link', { name: 'Associate Product Manager' })
    expect(screen.getByRole('button', { name: /Previous/ })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: /Next/ }))
    await waitFor(() => expect(jobCalls(mock).at(-1)?.searchParams.get('page')).toBe('2'))
  })

  it('returns to page one when a filter changes', async () => {
    const mock = stubFetch(jobsRoutes(page([job()], { total: 45, total_pages: 3 })))
    render(<JobsTable />)
    await screen.findByRole('link', { name: 'Associate Product Manager' })
    await userEvent.click(screen.getByRole('button', { name: /Next/ }))
    await waitFor(() => expect(jobCalls(mock).at(-1)?.searchParams.get('page')).toBe('2'))
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'all' } })
    await waitFor(() => {
      const last = jobCalls(mock).at(-1)?.searchParams
      expect(last?.get('status')).toBe('all')
      expect(last?.get('page')).toBe('1')
    })
  })

  it('sorts through the backend', async () => {
    const mock = stubFetch(jobsRoutes(page([job()])))
    render(<JobsTable />)
    await screen.findByRole('link', { name: 'Associate Product Manager' })
    await userEvent.click(screen.getByRole('button', { name: 'Company' }))
    await waitFor(() => {
      const last = jobCalls(mock).at(-1)?.searchParams
      expect(last?.get('sort_by')).toBe('company')
      expect(last?.get('sort_order')).toBe('asc')
    })
  })

  it('never offers a country filter', async () => {
    stubFetch(jobsRoutes(page([job()])))
    render(<JobsTable />)
    await screen.findByRole('link', { name: 'Associate Product Manager' })
    expect(screen.queryByLabelText(/country/i)).not.toBeInTheDocument()
    vi.restoreAllMocks()
  })
})
