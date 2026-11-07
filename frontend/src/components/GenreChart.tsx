'use client';

import React from 'react';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, Legend } from 'recharts';
import { Layers } from 'lucide-react';

interface GenreChartProps {
  genreBreakdown: Record<string, number>;
}

const COLORS = ['#6366f1', '#a855f7', '#ec4899', '#3b82f6', '#10b981', '#f59e0b', '#64748b'];

export default function GenreChart({ genreBreakdown }: GenreChartProps) {
  const data = Object.entries(genreBreakdown || {}).map(([name, value]) => ({
    name: name || 'General/Other',
    value,
  }));

  if (data.length === 0) {
    data.push({ name: 'No Data', value: 1 });
  }

  return (
    <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-6 shadow-xl backdrop-blur-sm flex flex-col h-full">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400">
            <Layers className="w-5 h-5" />
          </div>
          <h2 className="text-lg font-semibold text-white">Genre Distribution</h2>
        </div>
        <span className="text-xs text-slate-400 font-medium">Industry Classification</span>
      </div>

      <div className="flex-1 min-h-[260px] flex items-center justify-center">
        <ResponsiveContainer width="100%" height={260}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={65}
              outerRadius={95}
              paddingAngle={4}
              dataKey="value"
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} stroke="#1e293b" strokeWidth={2} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                backgroundColor: '#0f172a',
                borderColor: '#334155',
                borderRadius: '0.75rem',
                color: '#f8fafc',
                boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5)',
              }}
              itemStyle={{ color: '#f8fafc' }}
            />
            <Legend
              formatter={(value) => <span className="text-xs text-slate-300 font-medium">{value}</span>}
              layout="horizontal"
              verticalAlign="bottom"
              align="center"
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
