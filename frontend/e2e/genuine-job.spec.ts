import { expect, test } from '@playwright/test'

/**
 * Walks a genuine ingested job through the browser. The job is whatever the API
 * currently lists, so this proves the real path rather than a fixture.
 */
test('a genuine India job flows from the API to the dashboard, details page and CSV', async ({ page, request }) => {
  const listing = await (await request.get('/api/jobs?page_size=1')).json()
  test.skip(listing.total === 0, 'No genuine jobs are currently listed')
  const job = listing.items[0]
  expect(job.country_code).toBe('IN')
  expect(job.provenance).toBe('live_source')

  await page.goto('/')
  await expect(page.getByText('INDIA ONLY 🇮🇳')).toBeVisible()
  await expect(page.getByTestId('India-eligible jobs')).toHaveText(String(listing.total))

  const link = page.getByRole('link', { name: job.title, exact: true }).first()
  await expect(link).toBeVisible()

  const apply = page.getByRole('link', { name: `Apply for ${job.title} at ${job.company}` }).first()
  await expect(apply).toHaveAttribute('href', job.application_url)

  const applied = await request.get(job.application_url, { maxRedirects: 5, failOnStatusCode: false })
  expect(applied.status(), 'the original application page should load').toBeLessThan(500)

  await link.click()
  await expect(page).toHaveURL(new RegExp(`/jobs/${job.id}$`))
  await expect(page.getByRole('heading', { level: 1, name: job.title })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Why this is listed' })).toBeVisible()

  const csv = await (await request.get('/api/export/csv')).text()
  expect(csv).toContain(job.application_url)
})

test('search and filters narrow real results', async ({ page, request }) => {
  const all = await (await request.get('/api/jobs?page_size=1')).json()
  test.skip(all.total === 0, 'No genuine jobs are currently listed')
  const company: string = all.items[0].company

  await page.goto('/')
  await page.getByRole('searchbox', { name: 'Search jobs' }).fill(company)
  await expect(page.getByText(/Showing \d+ of \d+ matching jobs/)).toBeVisible()
  await expect(page.locator('tbody tr').first()).toContainText(company)

  await page.getByRole('searchbox', { name: 'Search jobs' }).fill('zzzz-no-such-job')
  await expect(page.getByText('No jobs match these filters')).toBeVisible()
})

test('source monitoring shows real health, including missing credentials', async ({ page }) => {
  await page.goto('/sources')
  await expect(page.getByRole('heading', { name: 'Source monitoring' })).toBeVisible()
  await expect(page.getByText('Needs credentials', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('Healthy', { exact: true }).first()).toBeVisible()
})
