export function formatDate(value: string | null | undefined): string {
  if (!value) return 'Not published'
  return new Date(value).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return 'Never'
  return new Date(value).toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatSalary(min: number | null, max: number | null, currency: string | null): string {
  if (min === null && max === null) return 'Not published'
  const amounts = [min, max].filter((value): value is number => value !== null)
  return `${currency ?? ''} ${amounts.map((value) => value.toLocaleString('en-IN')).join(' - ')}`.trim()
}

export function sourceLabel(name: string): string {
  const [kind, rest] = name.split(':')
  const labels: Record<string, string> = {
    greenhouse: 'Greenhouse',
    lever: 'Lever',
    ashby: 'Ashby',
    remotive: 'Remotive',
    rss: 'RSS',
    adzuna: 'Adzuna',
    manual: 'Manual',
  }
  return rest ? `${labels[kind] ?? kind} / ${rest}` : name
}
