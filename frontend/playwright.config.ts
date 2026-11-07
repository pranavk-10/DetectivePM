import { defineConfig } from '@playwright/test'

/* Runs against a real stack: PostgreSQL, FastAPI and Next must already be up. */
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  retries: 0,
  use: { baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:3000' },
})
