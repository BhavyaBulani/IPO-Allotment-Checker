import React, { useState, useEffect, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Loader2, Download, AlertCircle, CheckCircle2, XCircle, Clock, Search, FileText, X } from 'lucide-react';
import api from '../lib/api';

export default function ResultsDashboard() {
  const { batchId } = useParams();
  const [summary, setSummary] = useState(null);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Search
  const [searchQuery, setSearchQuery] = useState('');
  
  // Logs Modal
  const [showLogs, setShowLogs] = useState(false);
  const [logs, setLogs] = useState(null);
  const [logsLoading, setLogsLoading] = useState(false);
  
  // Pagination
  const [skip, setSkip] = useState(0);
  const [total, setTotal] = useState(0);
  const limit = 100; // Increased limit for better client-side search experience

  useEffect(() => {
    const fetchDashboardData = async () => {
      setLoading(true);
      try {
        const [summaryRes, resultsRes] = await Promise.all([
          api.get(`/results/batch/${batchId}/summary`),
          api.get(`/results/batch/${batchId}?skip=${skip}&limit=${limit}`)
        ]);
        setSummary(summaryRes.data);
        setResults(resultsRes.data.data);
        setTotal(resultsRes.data.total);
      } catch (err) {
        setError(err.response?.data?.detail || "Failed to load dashboard data.");
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, [batchId, skip]);

  const handleDownload = async () => {
    try {
      const res = await api.get(`/results/batch/${batchId}/export`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `IPO_Results_Batch_${batchId}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to export results.');
    }
  };
  
  const fetchLogs = async () => {
    setLogsLoading(true);
    setShowLogs(true);
    try {
      const res = await api.get(`/logs/${batchId}`);
      setLogs(res.data);
    } catch (err) {
      setLogs({ error: err.response?.data?.detail || "Failed to load run logs." });
    } finally {
      setLogsLoading(false);
    }
  };

  const filteredResults = useMemo(() => {
    if (!searchQuery) return results;
    const query = searchQuery.toLowerCase();
    return results.filter(r => 
      r.pan?.toLowerCase().includes(query) || 
      r.ipo_name?.toLowerCase().includes(query) ||
      r.status?.toLowerCase().includes(query)
    );
  }, [results, searchQuery]);

  if (error) {
    return (
      <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-[#f6f5f0] p-6">
        <div className="flex items-center gap-4 rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-700">
          <AlertCircle size={32} />
          <div>
            <h3 className="mb-1 text-lg font-bold">Error Loading Results</h3>
            <p>{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (loading && !summary) {
    return (
      <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-[#f6f5f0] text-stone-500">
        <Loader2 className="mr-3 animate-spin" size={24} /> Loading dashboard...
      </div>
    );
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#f6f5f0] p-6 pb-20">
      <div className="mx-auto max-w-6xl pt-8">
        <Link to="/" className="back-link mb-8">
          <ArrowLeft size={20} className="mr-2" /> Back to Home
        </Link>

        <div className="relative z-10 mb-8 flex flex-col items-start justify-between gap-4 md:flex-row md:items-end">
          <div>
            <h1 className="mb-2 text-3xl font-bold text-stone-900">Results Dashboard</h1>
            <p className="text-stone-500">Batch #{batchId}</p>
          </div>
          <div className="flex gap-3">
            <button 
              onClick={fetchLogs}
              className="btn-secondary"
            >
              <FileText size={20} />
              View Run Logs
            </button>
            <button 
              onClick={handleDownload}
              className="btn-primary"
            >
              <Download size={20} />
              Export to Excel
            </button>
          </div>
        </div>

        {summary && (
          <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-4">
            <div className="relative overflow-hidden rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
              <div className="absolute -right-4 -top-4 text-stone-100"><CheckCircle2 size={80} /></div>
              <p className="relative z-10 mb-1 text-sm text-stone-400">Total Processed</p>
              <p className="relative z-10 text-3xl font-bold text-stone-900">{summary.total_processed}</p>
            </div>
            
            <div className="relative overflow-hidden rounded-2xl border border-emerald-200 bg-emerald-50 p-5 shadow-sm">
              <div className="absolute -right-4 -top-4 text-emerald-100"><CheckCircle2 size={80} /></div>
              <p className="relative z-10 mb-1 text-sm text-emerald-700/70">Allotted</p>
              <p className="relative z-10 text-3xl font-bold text-emerald-700">{summary.allotted}</p>
            </div>
            
            <div className="relative overflow-hidden rounded-2xl border border-rose-200 bg-rose-50 p-5 shadow-sm">
              <div className="absolute -right-4 -top-4 text-rose-100"><XCircle size={80} /></div>
              <p className="relative z-10 mb-1 text-sm text-rose-700/70">Not Allotted</p>
              <p className="relative z-10 text-3xl font-bold text-rose-700">{summary.not_allotted}</p>
            </div>
            
            <div className="relative overflow-hidden rounded-2xl border border-amber-200 bg-amber-50 p-5 shadow-sm">
              <div className="absolute -right-4 -top-4 text-amber-100"><AlertCircle size={80} /></div>
              <p className="relative z-10 mb-1 text-sm text-amber-700/70">Errors / Invalid</p>
              <p className="relative z-10 text-3xl font-bold text-amber-700">{summary.errors + summary.invalid_pan}</p>
            </div>
          </div>
        )}

        <div className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
          <div className="flex items-center justify-between border-b border-stone-200 bg-stone-50 p-4">
            <div className="relative w-full max-w-md">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                <Search size={18} className="text-stone-400" />
              </div>
              <input
                type="text"
                placeholder="Search PAN, IPO, or Status..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-lg border border-stone-300 bg-white py-2 pl-10 pr-4 text-stone-800 placeholder-stone-400 focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600"
              />
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-stone-200 bg-stone-50 text-sm text-stone-500">
                  <th className="px-6 py-4 font-medium">Identifier</th>
                  <th className="px-6 py-4 font-medium">IPO</th>
                  <th className="px-6 py-4 font-medium">Registrar</th>
                  <th className="px-6 py-4 text-center font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {filteredResults.map((r, idx) => (
                  <tr key={idx} className="transition-colors hover:bg-stone-50">
                    <td className="px-6 py-4 font-mono text-sm text-stone-900">{r.pan}</td>
                    <td className="px-6 py-4 text-stone-600">{r.ipo_name}</td>
                    <td className="px-6 py-4 text-sm text-stone-400">{r.registrar_name}</td>
                    <td className="px-6 py-4 text-center">
                      <div className="flex flex-col items-center gap-1">
                        <span className={`inline-block rounded-full border px-3 py-1 text-xs font-bold
                          ${r.status === 'Allotted' ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 
                            r.status === 'Not Allotted' ? 'border-rose-200 bg-rose-50 text-rose-700' : 
                            'border-amber-200 bg-amber-50 text-amber-700'}`}
                        >
                          {r.status}
                        </span>
                        {r.served_from_cache && (
                          <span className="rounded border border-teal-200 bg-teal-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-teal-700">
                            ⚡ Cached
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {filteredResults.length === 0 && !loading && (
                  <tr>
                    <td colSpan="4" className="px-6 py-12 text-center text-stone-400">
                      No results found matching "{searchQuery}".
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          
          {total > limit && (
            <div className="flex items-center justify-between border-t border-stone-200 bg-stone-50 p-4 text-sm text-stone-500">
              <div>
                Showing {skip + 1} to {Math.min(skip + limit, total)} of {total} results
              </div>
              <div className="flex gap-2">
                <button 
                  disabled={skip === 0} 
                  onClick={() => setSkip(skip - limit)}
                  className="rounded-lg bg-white px-4 py-2 text-stone-700 transition-colors hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Previous
                </button>
                <button 
                  disabled={skip + limit >= total} 
                  onClick={() => setSkip(skip + limit)}
                  className="rounded-lg bg-white px-4 py-2 text-stone-700 transition-colors hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {showLogs && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-3xl border border-stone-200 bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-stone-200 bg-stone-50 p-6">
              <div className="flex items-center gap-3">
                <FileText className="text-teal-700" size={24} />
                <h2 className="text-xl font-bold text-stone-900">Run Logs</h2>
              </div>
              <button 
                onClick={() => setShowLogs(false)}
                className="rounded-full p-2 text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-700"
              >
                <X size={20} />
              </button>
            </div>
            
            <div className="flex-grow overflow-y-auto p-6">
              {logsLoading ? (
                <div className="flex items-center justify-center py-12 text-stone-400">
                  <Loader2 className="mr-3 animate-spin" size={24} /> Loading logs...
                </div>
              ) : logs?.error ? (
                <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-rose-700">
                  {logs.error}
                </div>
              ) : logs ? (
                <div className="space-y-6">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="rounded-xl border border-stone-200 bg-stone-50 p-4">
                      <p className="mb-1 text-sm text-stone-400">Started At</p>
                      <p className="font-mono text-stone-900">{logs.started_at ? new Date(logs.started_at).toLocaleString() : 'N/A'}</p>
                    </div>
                    <div className="rounded-xl border border-stone-200 bg-stone-50 p-4">
                      <p className="mb-1 text-sm text-stone-400">Completed At</p>
                      <p className="font-mono text-stone-900">{logs.completed_at ? new Date(logs.completed_at).toLocaleString() : 'N/A'}</p>
                    </div>
                  </div>
                  
                  <div className="rounded-xl border border-stone-200 bg-stone-50 p-5">
                    <h4 className="mb-4 flex items-center gap-2 font-medium text-stone-700">
                      <Clock size={16} /> Diagnostic Summary
                    </h4>
                    <div className="space-y-3">
                      <div className="flex items-center justify-between border-b border-stone-200/60 pb-2">
                        <span className="text-stone-500">Successful Queries</span>
                        <span className="font-mono font-bold text-emerald-700">{logs.success_count}</span>
                      </div>
                      <div className="flex items-center justify-between border-b border-stone-200/60 pb-2">
                        <span className="text-stone-500">Failed Queries</span>
                        <span className="font-mono font-bold text-rose-700">{logs.failure_count}</span>
                      </div>
                      <div className="flex items-center justify-between border-b border-stone-200/60 pb-2">
                        <span className="text-stone-500">Timeout Errors</span>
                        <span className="font-mono font-bold text-amber-700">{logs.timeout_count}</span>
                      </div>
                      <div className="flex items-center justify-between pb-2">
                        <span className="text-stone-500">Cache Hits</span>
                        <span className="font-mono font-bold text-teal-700">{logs.cache_hit_count}</span>
                      </div>
                    </div>
                  </div>
                  
                  <div>
                    <p className="mb-2 text-sm text-stone-400">Registrars Used</p>
                    <div className="flex flex-wrap gap-2">
                      {(logs.registrars_used || "").split(',').map(r => r.trim()).filter(Boolean).map((r, i) => (
                        <span key={i} className="rounded-full border border-stone-200 bg-stone-100 px-3 py-1 font-mono text-xs text-stone-600">
                          ID: {r}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
            <div className="border-t border-stone-200 bg-stone-50 p-6 text-right">
              <button 
                onClick={() => setShowLogs(false)}
                className="btn-secondary"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
