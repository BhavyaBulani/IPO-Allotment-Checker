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
      <div className="min-h-screen bg-slate-900 p-6 flex items-center justify-center">
        <div className="bg-red-500/10 p-6 rounded-2xl border border-red-500/30 text-red-400 flex items-center gap-4">
          <AlertCircle size={32} />
          <div>
            <h3 className="font-bold text-lg mb-1">Error Loading Results</h3>
            <p>{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (loading && !summary) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center text-slate-400">
        <Loader2 className="animate-spin mr-3" size={24} /> Loading dashboard...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900 p-6 pb-20">
      <div className="max-w-6xl mx-auto pt-8">
        <Link to="/" className="inline-flex items-center text-slate-400 hover:text-white mb-8 transition-colors">
          <ArrowLeft size={20} className="mr-2" /> Back to Home
        </Link>

        <div className="flex flex-col md:flex-row justify-between items-start md:items-end mb-8 gap-4 relative z-10">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">Results Dashboard</h1>
            <p className="text-slate-400">Batch #{batchId}</p>
          </div>
          <div className="flex gap-3">
            <button 
              onClick={fetchLogs}
              className="bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold py-2.5 px-4 rounded-xl transition-all border border-slate-700 flex items-center gap-2"
            >
              <FileText size={20} />
              View Run Logs
            </button>
            <button 
              onClick={handleDownload}
              className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2.5 px-6 rounded-xl transition-all shadow-lg shadow-indigo-500/20 flex items-center gap-2"
            >
              <Download size={20} />
              Export to Excel
            </button>
          </div>
        </div>

        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <div className="bg-slate-800/80 p-5 rounded-2xl border border-slate-700 relative overflow-hidden">
              <div className="absolute -right-4 -top-4 text-slate-700 opacity-20"><CheckCircle2 size={80} /></div>
              <p className="text-slate-400 text-sm mb-1 relative z-10">Total Processed</p>
              <p className="text-white text-3xl font-bold relative z-10">{summary.total_processed}</p>
            </div>
            
            <div className="bg-emerald-500/10 p-5 rounded-2xl border border-emerald-500/30 relative overflow-hidden">
              <div className="absolute -right-4 -top-4 text-emerald-500 opacity-10"><CheckCircle2 size={80} /></div>
              <p className="text-emerald-400/80 text-sm mb-1 relative z-10">Allotted</p>
              <p className="text-emerald-400 text-3xl font-bold relative z-10">{summary.allotted}</p>
            </div>
            
            <div className="bg-rose-500/10 p-5 rounded-2xl border border-rose-500/30 relative overflow-hidden">
              <div className="absolute -right-4 -top-4 text-rose-500 opacity-10"><XCircle size={80} /></div>
              <p className="text-rose-400/80 text-sm mb-1 relative z-10">Not Allotted</p>
              <p className="text-rose-400 text-3xl font-bold relative z-10">{summary.not_allotted}</p>
            </div>
            
            <div className="bg-amber-500/10 p-5 rounded-2xl border border-amber-500/30 relative overflow-hidden">
              <div className="absolute -right-4 -top-4 text-amber-500 opacity-10"><AlertCircle size={80} /></div>
              <p className="text-amber-400/80 text-sm mb-1 relative z-10">Errors / Invalid</p>
              <p className="text-amber-400 text-3xl font-bold relative z-10">{summary.errors + summary.invalid_pan}</p>
            </div>
          </div>
        )}

        <div className="bg-slate-800/80 rounded-2xl border border-slate-700 overflow-hidden shadow-xl">
          <div className="p-4 border-b border-slate-700 flex justify-between items-center bg-slate-900/50">
            <div className="relative w-full max-w-md">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Search size={18} className="text-slate-500" />
              </div>
              <input
                type="text"
                placeholder="Search PAN, IPO, or Status..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-slate-800 border border-slate-600 rounded-lg pl-10 pr-4 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors"
              />
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-900/50 border-b border-slate-700 text-slate-400 text-sm">
                  <th className="px-6 py-4 font-medium">Identifier</th>
                  <th className="px-6 py-4 font-medium">IPO</th>
                  <th className="px-6 py-4 font-medium">Registrar</th>
                  <th className="px-6 py-4 font-medium text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {filteredResults.map((r, idx) => (
                  <tr key={idx} className="hover:bg-slate-800/50 transition-colors">
                    <td className="px-6 py-4 text-white font-mono text-sm">{r.pan}</td>
                    <td className="px-6 py-4 text-slate-300">{r.ipo_name}</td>
                    <td className="px-6 py-4 text-slate-400 text-sm">{r.registrar_name}</td>
                    <td className="px-6 py-4 text-center">
                      <div className="flex flex-col items-center gap-1">
                        <span className={`px-3 py-1 rounded-full text-xs font-bold inline-block
                          ${r.status === 'Allotted' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 
                            r.status === 'Not Allotted' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 
                            'bg-amber-500/10 text-amber-400 border border-amber-500/20'}`}
                        >
                          {r.status}
                        </span>
                        {r.served_from_cache && (
                          <span className="text-[10px] text-indigo-400 font-semibold tracking-wider uppercase bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                            ⚡ Cached
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {filteredResults.length === 0 && !loading && (
                  <tr>
                    <td colSpan="4" className="px-6 py-12 text-center text-slate-500">
                      No results found matching "{searchQuery}".
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          
          {total > limit && (
            <div className="p-4 border-t border-slate-700 bg-slate-900/30 flex justify-between items-center text-sm text-slate-400">
              <div>
                Showing {skip + 1} to {Math.min(skip + limit, total)} of {total} results
              </div>
              <div className="flex gap-2">
                <button 
                  disabled={skip === 0} 
                  onClick={() => setSkip(skip - limit)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-white transition-colors"
                >
                  Previous
                </button>
                <button 
                  disabled={skip + limit >= total} 
                  onClick={() => setSkip(skip + limit)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-white transition-colors"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {showLogs && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-3xl w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
            <div className="p-6 border-b border-slate-800 flex justify-between items-center bg-slate-800/50">
              <div className="flex items-center gap-3">
                <FileText className="text-indigo-400" size={24} />
                <h2 className="text-xl font-bold text-white">Run Logs</h2>
              </div>
              <button 
                onClick={() => setShowLogs(false)}
                className="text-slate-400 hover:text-white p-2 rounded-full hover:bg-slate-800 transition-colors"
              >
                <X size={20} />
              </button>
            </div>
            
            <div className="p-6 overflow-y-auto flex-grow">
              {logsLoading ? (
                <div className="flex justify-center items-center py-12 text-slate-400">
                  <Loader2 className="animate-spin mr-3" size={24} /> Loading logs...
                </div>
              ) : logs?.error ? (
                <div className="bg-red-500/10 p-4 rounded-xl border border-red-500/30 text-red-400">
                  {logs.error}
                </div>
              ) : logs ? (
                <div className="space-y-6">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-slate-800/50 p-4 rounded-xl border border-slate-700">
                      <p className="text-slate-500 text-sm mb-1">Started At</p>
                      <p className="text-white font-mono">{logs.started_at ? new Date(logs.started_at).toLocaleString() : 'N/A'}</p>
                    </div>
                    <div className="bg-slate-800/50 p-4 rounded-xl border border-slate-700">
                      <p className="text-slate-500 text-sm mb-1">Completed At</p>
                      <p className="text-white font-mono">{logs.completed_at ? new Date(logs.completed_at).toLocaleString() : 'N/A'}</p>
                    </div>
                  </div>
                  
                  <div className="bg-slate-800/30 rounded-xl border border-slate-700 p-5">
                    <h4 className="text-slate-300 font-medium mb-4 flex items-center gap-2">
                      <Clock size={16} /> Diagnostic Summary
                    </h4>
                    <div className="space-y-3">
                      <div className="flex justify-between items-center border-b border-slate-700/50 pb-2">
                        <span className="text-slate-400">Successful Queries</span>
                        <span className="text-emerald-400 font-mono font-bold">{logs.success_count}</span>
                      </div>
                      <div className="flex justify-between items-center border-b border-slate-700/50 pb-2">
                        <span className="text-slate-400">Failed Queries</span>
                        <span className="text-rose-400 font-mono font-bold">{logs.failure_count}</span>
                      </div>
                      <div className="flex justify-between items-center border-b border-slate-700/50 pb-2">
                        <span className="text-slate-400">Timeout Errors</span>
                        <span className="text-amber-400 font-mono font-bold">{logs.timeout_count}</span>
                      </div>
                      <div className="flex justify-between items-center pb-2">
                        <span className="text-slate-400">Cache Hits</span>
                        <span className="text-indigo-400 font-mono font-bold">{logs.cache_hit_count}</span>
                      </div>
                    </div>
                  </div>
                  
                  <div>
                    <p className="text-slate-500 text-sm mb-2">Registrars Used</p>
                    <div className="flex gap-2 flex-wrap">
                      {(logs.registrars_used || "").split(',').map(r => r.trim()).filter(Boolean).map((r, i) => (
                        <span key={i} className="bg-slate-800 text-slate-300 px-3 py-1 rounded-full text-xs font-mono border border-slate-700">
                          ID: {r}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
            <div className="p-6 border-t border-slate-800 bg-slate-900/50 text-right">
              <button 
                onClick={() => setShowLogs(false)}
                className="bg-slate-700 hover:bg-slate-600 text-white font-semibold py-2 px-6 rounded-xl transition-colors"
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
