'use client'

import React, { useState } from 'react'
import { Search, RefreshCw, Download, FileSpreadsheet, CheckCircle2, AlertCircle } from 'lucide-react'
import { triggerScrape, syncGSheets, getExportUrl } from '@/lib/api'

interface HeaderProps {
  isRunning: boolean
  onScrapeComplete: () => void
}

export default function Header({ isRunning, onScrapeComplete }: HeaderProps) {
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [spreadsheetId, setSpreadsheetId] = useState('')

  const handleManualScrape = async () => {
    setLoading(true)
    setMessage(null)
    try {
      const res = await triggerScrape()
      setMessage({ type: 'success', text: res.message })
      onScrapeComplete()
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Scrape failed' })
    } finally {
      setLoading(false)
    }
  }

  const handleSyncGSheets = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!spreadsheetId.trim()) return

    setSyncing(true)
    setMessage(null)
    try {
      const res = await syncGSheets(spreadsheetId.trim())
      setMessage({ type: 'success', text: res.message })
      setShowModal(false)
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Google Sheets sync failed' })
    } finally {
      setSyncing(false)
    }
  }

  return (
    <header className="flex flex-col gap-4 pb-6 border-b border-slate-800/80 md:flex-row md:items-center md:justify-between">
      {/* Title & Status */}
      <div className="flex items-start space-x-4">
        <div className="rounded-2xl bg-gradient-to-tr from-indigo-600 to-purple-600 p-3.5 shadow-xl shadow-indigo-500/20 text-white">
          <Search className="h-7 w-7" />
        </div>
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">DetectivePM</h1>
            <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>Live Scraper Active</span>
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-400">
            Automated job-scraping and analytics dashboard for Product Management roles
          </p>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex flex-wrap items-center gap-3">
        {message && (
          <div className={`text-xs px-3 py-2 rounded-xl flex items-center space-x-1.5 border ${
            message.type === 'success'
              ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'
              : 'bg-rose-500/10 text-rose-300 border-rose-500/20'
          }`}>
            {message.type === 'success' ? <CheckCircle2 className="h-4 w-4 shrink-0" /> : <AlertCircle className="h-4 w-4 shrink-0" />}
            <span className="truncate max-w-[200px]">{message.text}</span>
          </div>
        )}

        <a
          href={getExportUrl()}
          download="detective_pm_jobs.csv"
          className="flex items-center space-x-2 rounded-xl bg-slate-900 border border-slate-800 px-4 py-2.5 text-sm font-semibold text-slate-200 hover:bg-slate-800 hover:text-white transition-all shadow-sm"
        >
          <Download className="h-4 w-4 text-indigo-400" />
          <span>Export CSV</span>
        </a>

        <button
          onClick={() => setShowModal(true)}
          className="flex items-center space-x-2 rounded-xl bg-slate-900 border border-slate-800 px-4 py-2.5 text-sm font-semibold text-slate-200 hover:bg-slate-800 hover:text-white transition-all shadow-sm"
        >
          <FileSpreadsheet className="h-4 w-4 text-emerald-400" />
          <span>Sync GSheets</span>
        </button>

        <button
          onClick={handleManualScrape}
          disabled={loading}
          className="flex items-center space-x-2 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-600/25 hover:from-indigo-500 hover:to-purple-500 disabled:opacity-50 transition-all"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          <span>{loading ? 'Scraping...' : 'Trigger Manual Scrape'}</span>
        </button>
      </div>

      {/* Google Sheets Sync Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl bg-slate-900 border border-slate-800 p-6 shadow-2xl">
            <h3 className="text-lg font-bold text-white mb-2">Sync to Google Sheets</h3>
            <p className="text-sm text-slate-400 mb-4">
              Enter your Google Spreadsheet ID (from the sheet URL) to sync the latest scraped PM job posts.
            </p>
            <form onSubmit={handleSyncGSheets} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">Spreadsheet ID</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
                  value={spreadsheetId}
                  onChange={(e) => setSpreadsheetId(e.target.value)}
                  className="w-full rounded-xl bg-slate-950 px-4 py-2.5 text-sm text-white placeholder-slate-600 border border-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <div className="flex justify-end space-x-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 rounded-xl bg-slate-800 text-sm font-medium text-slate-300 hover:bg-slate-700 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={syncing}
                  className="px-4 py-2 rounded-xl bg-indigo-600 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
                >
                  {syncing ? 'Syncing...' : 'Start Sync'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </header>
  )
}
