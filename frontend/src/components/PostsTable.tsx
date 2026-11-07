'users client';

import React, { useState, useEffect } from 'react';
import { Search, Filter, Mail, Phone, ExternalLink, ChevronLeft, ChevronRight, User, Calendar } from 'lucide-react';
import { fetchPosts, Post } from '@/lib/api';

interface PostsTableProps {
  refreshTrigger: number;
}

export default function PostsTable({ refreshTrigger }: PostsTableProps) {
  const [posts, setPosts] = useState<Post[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [totalPages, setTotalPages] = useState(1);
  const [roleType, setRoleType] = useState('All');
  const [genre, setGenre] = useState('All');
  const [searchTerm, setSearchTerm] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const genres = ['All', 'SaaS', 'B2C', 'FinTech', 'EdTech', 'HealthTech', 'General/Other'];
  const roleTypes = ['All', 'Intern', 'Full-time'];

  const loadPosts = async () => {
    try {
      setLoading(true);
      const res = await fetchPosts({
        page,
        page_size: pageSize,
        role_type: roleType,
        genre,
        search: searchTerm,
      });
      setPosts(res.posts);
      setTotal(res.total);
      setTotalPages(res.total_pages);
    } catch (err) {
      console.error('Failed to fetch posts:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPosts();
  }, [page, roleType, genre, searchTerm, refreshTrigger]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    setSearchTerm(searchInput);
  };

  return (
    <div className="rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl backdrop-blur-sm overflow-hidden flex flex-col">
      {/* Table Toolbar */}
      <div className="p-5 border-b border-slate-800 flex flex-col md:flex-row items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-white">Scraped Job Posts</h2>
          <p className="text-xs text-slate-400">Showing {posts.length} of {total} total extracted PM roles</p>
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          {/* Search Bar */}
          <form onSubmit={handleSearchSubmit} className="relative flex-1 md:w-64">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search content or author..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full pl-9 pr-4 py-2 rounded-xl bg-slate-950 border border-slate-700 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-all"
            />
          </form>

          {/* Role Filter */}
          <select
            value={roleType}
            onChange={(e) => { setRoleType(e.target.value); setPage(1); }}
            className="px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 transition-all"
          >
            {roleTypes.map((r) => (
              <option key={r} value={r}>{r === 'All' ? 'All Roles' : r}</option>
            ))}
          </select>

          {/* Genre Filter */}
          <select
            value={genre}
            onChange={(e) => { setGenre(e.target.value); setPage(1); }}
            className="px-3 py-2 rounded-xl bg-slate-950 border border-slate-700 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 transition-all"
          >
            {genres.map((g) => (
              <option key={g} value={g}>{g === 'All' ? 'All Genres' : g}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Table View */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-800 bg-slate-950/50 text-xs font-semibold text-slate-400 uppercase tracking-wider">
              <th className="py-3 px-5">Author / Account</th>
              <th className="py-3 px-5">Role & Genre</th>
              <th className="py-3 px-5">Post Content Preview</th>
              <th className="py-3 px-5">Contacts</th>
              <th className="py-3 px-5">Timestamp</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 text-sm">
            {loading ? (
              [1, 2, 3, 4, 5].map((i) => (
                <tr key={i} className="animate-pulse">
                  <td colSpan={5} className="py-4 px-5">
                    <div className="h-6 bg-slate-800 rounded-lg w-full" />
                  </td>
                </tr>
              ))
            ) : posts.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-12 text-center text-slate-500">
                  No job posts found matching your criteria. Try triggering a manual scrape!
                </td>
              </tr>
            ) : (
              posts.map((post) => {
                const isExpanded = expandedId === post.post_id;
                return (
                  <tr key={post.post_id} className="hover:bg-slate-800/30 transition-colors">
                    {/* Author */}
                    <td className="py-4 px-5 align-top">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 flex items-center justify-center font-bold text-xs shrink-0">
                          {post.name ? post.name.charAt(0).toUpperCase() : 'P'}
                        </div>
                        <div>
                          <div className="font-medium text-white">{post.name || 'Anonymous'}</div>
                          <a
                            href={post.account_id}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-indigo-400 hover:underline flex items-center gap-1 mt-0.5"
                          >
                            Profile <ExternalLink className="w-3 h-3" />
                          </a>
                        </div>
                      </div>
                    </td>

                    {/* Role & Genre */}
                    <td className="py-4 px-5 align-top whitespace-nowrap">
                      <div className="flex flex-col gap-1.5">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold w-fit ${
                          post.role_type === 'Intern'
                            ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                            : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        }`}>
                          {post.role_type}
                        </span>
                        <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-slate-800 text-slate-300 w-fit border border-slate-700">
                          {post.genre || 'General/Other'}
                        </span>
                      </div>
                    </td>

                    {/* Content Preview */}
                    <td className="py-4 px-5 align-top max-w-md">
                      <div className="text-slate-300 text-sm leading-relaxed">
                        {isExpanded ? post.post_content : `${post.post_content.substring(0, 140)}...`}
                      </div>
                      {post.post_content.length > 140 && (
                        <button
                          onClick={() => setExpandedId(isExpanded ? null : post.post_id)}
                          className="text-xs text-indigo-400 hover:text-indigo-300 font-semibold mt-1"
                        >
                          {isExpanded ? 'Show less' : 'Read more'}
                        </button>
                      )}
                    </td>

                    {/* Contacts */}
                    <td className="py-4 px-5 align-top">
                      <div className="text-xs text-slate-400">
                        {post.contacts_present && post.contacts_present !== 'None' ? (
                          <div className="flex items-center gap-1.5 text-indigo-300 bg-indigo-500/10 px-2.5 py-1 rounded-lg border border-indigo-500/20 w-fit">
                            <Mail className="w-3.5 h-3.5" />
                            <span>{post.contacts_present}</span>
                          </div>
                        ) : (
                          <span className="text-slate-600">None extracted</span>
                        )}
                      </div>
                    </td>

                    {/* Timestamp */}
                    <td className="py-4 px-5 align-top whitespace-nowrap text-xs text-slate-400">
                      <div className="flex items-center gap-1.5">
                        <Calendar className="w-3.5 h-3.5 text-slate-500" />
                        <span>{new Date(post.timestamp).toLocaleDateString()}</span>
                      </div>
                      <div className="text-slate-500 mt-0.5">
                        {new Date(post.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      <div className="p-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400 bg-slate-950/30">
        <div>
          Page <span className="font-semibold text-white">{page}</span> of <span className="font-semibold text-white">{totalPages || 1}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(p - 1, 1))}
            disabled={page === 1}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            <ChevronLeft className="w-4 h-4" /> Previous
          </button>
          <button
            onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
            disabled={page >= totalPages}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            Next <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
