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
      case 'Completed': return <CheckCircle2 className="text-emerald-600" size={18} />;
      case 'Failed': return <XCircle className="text-rose-600" size={18} />;
      case 'In Progress': return <Loader2 className="animate-spin text-teal-600" size={18} />;
      default: return <Clock className="text-stone-400" size={18} />;
    }
  };

  const getStatusBadgeClass = (status) => {
    switch(status) {
      case 'Completed': return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'Failed': return 'bg-rose-50 text-rose-700 border-rose-200';
      case 'In Progress': return 'bg-teal-50 text-teal-700 border-teal-200';
      default: return 'bg-stone-100 text-stone-600 border-stone-200';
    }
  };

  if (error) {
    return (
      <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-[#f6f5f0] p-6">
        <div className="flex items-center gap-4 rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-700">
          <AlertCircle size={32} />
          <div>
            <h3 className="mb-1 text-lg font-bold">Error Loading History</h3>
            <p>{error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#f6f5f0] p-6 pb-20">
      <div className="mx-auto max-w-6xl pt-8">
        <Link to="/" className="back-link mb-8">
          <ArrowLeft size={20} className="mr-2" /> Back to Home
        </Link>

        <div className="relative z-10 mb-8">
          <h1 className="mb-2 text-3xl font-bold text-stone-900">Run History</h1>
          <p className="text-stone-500">View and access past batch processing results.</p>
        </div>

        <div className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-stone-200 bg-stone-50 text-sm text-stone-500">
                  <th className="px-6 py-4 font-medium">Batch ID</th>
                  <th className="px-6 py-4 font-medium">Upload Date</th>
                  <th className="px-6 py-4 font-medium">File Name</th>
                  <th className="px-6 py-4 font-medium">Valid Rows</th>
                  <th className="px-6 py-4 font-medium">Status</th>
                  <th className="px-6 py-4 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {loading && batches.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="px-6 py-12 text-center text-stone-400">
                      <Loader2 className="mr-2 inline animate-spin" size={20} /> Loading...
                    </td>
                  </tr>
                ) : (
                  batches.map((b) => (
                    <tr key={b.id} className="transition-colors hover:bg-stone-50">
                      <td className="px-6 py-4 font-mono text-sm text-stone-900">#{b.id}</td>
                      <td className="px-6 py-4 text-sm text-stone-500">
                        {new Date(b.uploaded_at).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 text-stone-600">
                        <div className="flex items-center gap-2">
                          <FileText size={16} className="text-stone-400" />
                          {b.file_name}
                        </div>
                      </td>
                      <td className="px-6 py-4 font-mono text-stone-600">{b.valid_row_count}</td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs font-bold ${getStatusBadgeClass(b.status)}`}>
                          {getStatusIcon(b.status)}
                          {b.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button 
                          onClick={() => navigate(b.status === 'Completed' ? `/results/${b.id}` : `/progress/${b.id}`)}
                          className="rounded-lg border border-teal-200 bg-teal-50 px-4 py-2 text-sm text-teal-700 transition-colors hover:bg-teal-100"
                        >
                          {b.status === 'Completed' ? 'View Dashboard' : 'View Progress'}
                        </button>
                      </td>
                    </tr>
                  ))
                )}
                {!loading && batches.length === 0 && (
                  <tr>
                    <td colSpan="6" className="px-6 py-12 text-center text-stone-400">
                      No run history found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          
          {total > limit && (
            <div className="flex items-center justify-between border-t border-stone-200 bg-stone-50 p-4 text-sm text-stone-500">
              <div>
                Showing {skip + 1} to {Math.min(skip + limit, total)} of {total} runs
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
    </div>
  );
}
