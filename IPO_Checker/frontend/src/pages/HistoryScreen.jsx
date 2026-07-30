import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2, AlertCircle, FileText, CheckCircle2, XCircle, Clock } from 'lucide-react';
import api from '../lib/api';

export default function HistoryScreen() {
  const navigate = useNavigate();
  const [batches, setBatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const [skip, setSkip] = useState(0);
  const [total, setTotal] = useState(0);
  const limit = 20;

  useEffect(() => {
    const fetchHistory = async () => {
      setLoading(true);
      try {
        const res = await api.get(`/history/batches?skip=${skip}&limit=${limit}`);
        setBatches(res.data.data);
        setTotal(res.data.total);
      } catch (err) {
        setError(err.response?.data?.detail || "Failed to load run history.");
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, [skip]);

  const getStatusIcon = (status) => {
    switch(status) {
      case 'Completed': return <CheckCircle2 className="text-emerald-400" size={18} />;
      case 'Failed': return <XCircle className="text-rose-400" size={18} />;
      case 'In Progress': return <Loader2 className="animate-spin text-indigo-400" size={18} />;
      default: return <Clock className="text-slate-400" size={18} />;
    }
  };

  const getStatusBadgeClass = (status) => {
    switch(status) {
      case 'Completed': return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      case 'Failed': return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
      case 'In Progress': return 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20';
      default: return 'bg-slate-700 text-slate-300 border-slate-600';
    }
  };

  if (error) {
    return (
      <div className="min-h-screen bg-slate-900 p-6 flex items-center justify-center">
        <div className="bg-red-500/10 p-6 rounded-2xl border border-red-500/30 text-red-400 flex items-center gap-4">
          <AlertCircle size={32} />
          <div>
            <h3 className="font-bold text-lg mb-1">Error Loading History</h3>
            <p>{error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900 p-6 pb-20">
      <div className="max-w-6xl mx-auto pt-8">
        <Link to="/" className="inline-flex items-center text-slate-400 hover:text-white mb-8 transition-colors">
          <ArrowLeft size={20} className="mr-2" /> Back to Home
        </Link>

        <div className="mb-8 relative z-10">
          <h1 className="text-3xl font-bold text-white mb-2">Run History</h1>
          <p className="text-slate-400">View and access past batch processing results.</p>
        </div>

        <div className="bg-slate-800/80 rounded-2xl border border-slate-700 overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-900/50 border-b border-slate-700 text-slate-400 text-sm">
                  <th className="px-6 py-4 font-medium">Batch ID</th>
                  <th className="px-6 py-4 font-medium">Upload Date</th>
                  <th className="px-6 py-4 font-medium">File Name</th>
                  <th className="px-6 py-4 font-medium">Valid Rows</th>
                  <th className="px-6 py-4 font-medium">Status</th>
                  <th className="px-6 py-4 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {loading && batches.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="px-6 py-12 text-center text-slate-500">
                      <Loader2 className="animate-spin inline mr-2" size={20} /> Loading...
                    </td>
                  </tr>
                ) : (
                  batches.map((b) => (
                    <tr key={b.id} className="hover:bg-slate-800/50 transition-colors">
                      <td className="px-6 py-4 text-white font-mono text-sm">#{b.id}</td>
                      <td className="px-6 py-4 text-slate-300 text-sm">
                        {new Date(b.uploaded_at).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 text-slate-300">
                        <div className="flex items-center gap-2">
                          <FileText size={16} className="text-slate-500" />
                          {b.file_name}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-slate-300 font-mono">{b.valid_row_count}</td>
                      <td className="px-6 py-4">
                        <span className={`px-3 py-1 rounded-full text-xs font-bold inline-flex items-center gap-1 border ${getStatusBadgeClass(b.status)}`}>
                          {getStatusIcon(b.status)}
                          {b.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button 
                          onClick={() => navigate(b.status === 'Completed' ? `/results/${b.id}` : `/progress/${b.id}`)}
                          className="text-sm bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 px-4 py-2 rounded-lg transition-colors border border-indigo-500/20"
                        >
                          {b.status === 'Completed' ? 'View Dashboard' : 'View Progress'}
                        </button>
                      </td>
                    </tr>
                  ))
                )}
                {!loading && batches.length === 0 && (
                  <tr>
                    <td colSpan="6" className="px-6 py-12 text-center text-slate-500">
                      No run history found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          
          {total > limit && (
            <div className="p-4 border-t border-slate-700 bg-slate-900/30 flex justify-between items-center text-sm text-slate-400">
              <div>
                Showing {skip + 1} to {Math.min(skip + limit, total)} of {total} runs
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
    </div>
  );
}
