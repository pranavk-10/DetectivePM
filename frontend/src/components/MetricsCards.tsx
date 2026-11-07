'use client';

import React from 'react';
import { Database, GraduationCap, Briefcase, Clock, TrendingUp } from 'lucide-react';
import { StatsResponse } from '@/lib/api';

interface MetricsCardsProps {
  stats: StatsResponse | null;
  loading: boolean;
}

export default function MetricsCards({ stats, loading }: MetricsCardsProps) {
  if (loading && !stats) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-32 rounded-2xl bg-slate-900/50 border border-slate-800 animate-pulse" />
        ))}
      </div>
    );
  }

  const total = stats?.total_posts || 0;
  const interns = stats?.intern_count || 0;
  const fulltime = stats?.fulltime_count || 0;
  const lastUpdate = stats?.last_scrape 
    ? new Date(stats.last_scrape).toLocaleString() 
    : 'Never';

  const internPercentage = total > 0 ? Math.round((interns / total) * 100) : 0;
  const fulltimePercentage = total > 0 ? Math.round((fulltime / total) * 100) : 0;

  const cards = [
    {
      title: 'Total Scraped Posts',
      value: total.toLocaleString(),
      subtext: 'Deduplicated records in SQLite',
      icon: Database,
      gradient: 'from-blue-500/20 via-indigo-500/10 to-transparent',
      borderColor: 'border-blue-500/30',
      iconColor: 'text-blue-400 bg-blue-500/10',
    },
    {
      title: 'Internships Found',
      value: interns.toLocaleString(),
      subtext: `${internPercentage}% of total roles`,
      icon: GraduationCap,
      gradient: 'from-purple-500/20 via-fuchsia-500/10 to-transparent',
      borderColor: 'border-purple-500/30',
      iconColor: 'text-purple-400 bg-purple-500/10',
    },
    {
      title: 'Full-Time Roles',
      value: fulltime.toLocaleString(),
      subtext: `${fulltimePercentage}% of total roles`,
      icon: Briefcase,
      gradient: 'from-emerald-500/20 via-teal-500/10 to-transparent',
      borderColor: 'border-emerald-500/30',
      iconColor: 'text-emerald-400 bg-emerald-500/10',
    },
    {
      title: 'Last Scrape Timestamp',
      value: lastUpdate,
      subtext: stats?.scheduler?.next_run ? `Next: ${new Date(stats.scheduler.next_run).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : 'Auto-syncing every 5h',
      icon: Clock,
      gradient: 'from-amber-500/20 via-orange-500/10 to-transparent',
      borderColor: 'border-amber-500/30',
      iconColor: 'text-amber-400 bg-amber-500/10',
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
      {cards.map((card, idx) => {
        const Icon = card.icon;
        return (
          <div
            key={idx}
            className={`relative overflow-hidden rounded-2xl bg-gradient-to-b ${card.gradient} bg-slate-900/90 border ${card.borderColor} p-6 shadow-xl backdrop-blur-sm transition-all hover:border-slate-700`}
          >
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm font-medium text-slate-400">{card.title}</span>
              <div className={`p-2.5 rounded-xl ${card.iconColor}`}>
                <Icon className="w-5 h-5" />
              </div>
            </div>
            <div className="text-3xl font-extrabold tracking-tight text-white mb-1">
              {card.value}
            </div>
            <div className="text-xs text-slate-400 flex items-center gap-1.5 font-medium">
              <TrendingUp className="w-3.5 h-3.5 text-indigo-400" />
              {card.subtext}
            </div>
          </div>
        );
      })}
    </div>
  );
}
