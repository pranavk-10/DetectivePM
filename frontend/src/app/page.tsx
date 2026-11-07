'use client'

import React, { useState, useEffect, useCallback } from 'react'
import Header from '@/components/Header'
import MetricsCards from '@/components/MetricsCards'
import GenreChart from '@/components/GenreChart'
import PostsTable from '@/components/PostsTable'
import { fetchStats, fetchPosts, PostItem, StatsResponse } from '@/lib/api'

export default function DashboardPage() {
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [postsData, setPostsData] = useState<{ items: PostItem[]; total: number }>({ items: [], total: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filter & Pagination state
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [roleType, setRoleType] = useState('')
  const [genre, setGenre] = useState('')
  const [search, setSearch] = useState('')

  const loadData = useCallback(async () => {
    try {
      setError(null)
      const [statsRes, postsRes] = await Promise.all([
        fetchStats(),
        fetchPosts({ page, page_size: pageSize, role_type: roleType || undefined, genre: genre || undefined, search: search || undefined }),
      ])
      setStats(statsRes)
      setPostsData(postsRes)
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard data. Ensure backend is running.')
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, roleType, genre, search])

  // Initial load & 30s auto-refresh
  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 30000)
    return () => clearInterval(interval)
  }, [loadData])

  // Reset page when filters change
  const handleRoleTypeChange = (val: string) => {
    setRoleType(val)
    setPage(1)
  }

  const handleGenreChange = (val: string) => {
    setGenre(val)
    setPage(1)
  }

  const handleSearchChange = (val: string) => {
    setSearch(val)
    setPage(1)
  }

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col">
      <div className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <Header
          isRunning={stats?.scheduler?.is_running ?? true}
          onScrapeComplete={loadData}
        />

        {error && (
          <div className="rounded-2xl bg-rose-500/10 border border-rose-500/20 p-4 text-rose-300 text-sm flex items-center justify-between">
            <span>{error}</span>
            <button onClick={loadData} className="underline text-xs font-semibold hover:text-rose-200">Retry</button>
          </div>
        )}

        {/* Metrics Cards */}
        <MetricsCards
          totalPosts={stats?.total_posts ?? 0}
          internCount={stats?.intern_count ?? 0}
          fulltimeCount={stats?.fulltime_count ?? 0}
          lastUpdated={stats?.last_scrape_time ?? null}
          nextRun={stats?.scheduler?.next_run ?? null}
        />

        {/* Charts & Analytics Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-1">
            <GenreChart data={stats?.genre_breakdown ?? {}} />
          </div>
          <div className="lg:col-span-2">
            {/* Additional analytics summary or quick insight card */}
            <div className="h-full rounded-2xl bg-gradient-to-br from-slate-900/90 to-slate-900/50 p-6 border border-slate-800/80 shadow-xl backdrop-blur-xl flex flex-col justify-between">
              <div>
                <h3 className="text-lg font-semibold text-white mb-2">DetectivePM Intelligence Suite</h3>
                <p className="text-sm text-slate-400 mb-6">
                  Automated scraping engine continuously monitors LinkedIn for PM internships and junior/associate full-time opportunities. Contact info and recruiter details are automatically extracted and deduplicated.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
                  <div className="rounded-xl bg-slate-950/60 p-4 border border-slate-800/80">
                    <p className="text-xs text-slate-400">Scrape Frequency</p>
                    <p className="mt-1 text-lg font-bold text-white">Every 5 Hours</p>
                  </div>
                  <div className="rounded-xl bg-slate-950/60 p-4 border border-slate-800/80">
                    <p className="text-xs text-slate-400">Deduplication</p>
                    <p className="mt-1 text-lg font-bold text-emerald-400">SHA-256 Unique</p>
                  </div>
                  <div className="rounded-xl bg-slate-950/60 p-4 border border-slate-800/80">
                    <p className="text-xs text-slate-400">Storage Format</p>
                    <p className="mt-1 text-lg font-bold text-indigo-400">SQLite + CSV</p>
                  </div>
                </div>
              </div>
              <div className="text-xs text-slate-500 pt-4 border-t border-slate-800/80 flex items-center justify-between">
                <span>System Status: Fully Operational</span>
                <span>Auto-refresh active (30s)</span>
              </div>
            </div>
          </div>
        </div>

        {/* Posts Table */}
        <PostsTable
          posts={postsData.items}
          total={postsData.total}
          page={page}
          pageSize={pageSize}
          roleType={roleType}
          genre={genre}
          search={search}
          onPageChange={setPage}
          onRoleTypeChange={handleRoleTypeChange}
          onGenreChange={handleGenreChange}
          onSearchChange={handleSearchChange}
        />
      </div>
    </div>
  )
}
