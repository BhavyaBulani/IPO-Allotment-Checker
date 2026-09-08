import React, { useState, useEffect } from 'react';
import { useParams, Link, useLocation } from 'react-router-dom';
import { ArrowLeft, Loader2, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';
import api from '../lib/api';

export default function ProgressScreen() {
  const { batchId } = useParams();
  const location = useLocation();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let intervalId;

    const fetchProgress = async () => {
      try {
        const res = await api.get(`/progress/${batchId}`);
        setData(res.data);

        // Stop polling if completed or failed
        if (res.data.status === 'Completed' || res.data.status === 'Failed') {
          clearInterval(intervalId);
        }
      } catch (err) {
        setError(err.response?.data?.detail || "Failed to fetch progress.");
        clearInterval(intervalId);
      }
    };

    fetchProgress(); // Initial fetch
    intervalId = setInterval(fetchProgress, 2000); // Poll every 2 seconds

    return () => clearInterval(intervalId);
  }, [batchId]);

  if (error) {
    return (
      <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-[#f6f5f0] p-6">
        <div className="flex items-center gap-4 rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-700">
          <AlertCircle size={32} />
          <div>
            <h3 className="mb-1 text-lg font-bold">Error</h3>
            <p>{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-[#f6f5f0] p-6 text-stone-500">
        <Loader2 className="mr-3 animate-spin" size={24} /> Loading batch {batchId}...
      </div>
    );
  }

  const isComplete = data.status === 'Completed';

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#f6f5f0] p-6">
      <div className="mx-auto max-w-3xl pt-10">
        <Link to="/" className="back-link mb-8">
          <ArrowLeft size={20} className="mr-2" /> Back to Home
        </Link>

        {location.state?.skippedBigshare?.length > 0 && (
          <div className="mb-6 flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-5 text-amber-800">
            <AlertCircle size={20} className="mt-0.5 shrink-0" />
            <div>
              <p className="font-semibold">Some IPOs were skipped</p>
              <p className="text-sm">
                Bigshare IPOs require a manually-typed CAPTCHA and cannot be checked in
                bulk. Use Single Client Check for:{' '}
                {location.state.skippedBigshare.join(', ')}.
              </p>
            </div>
          </div>
        )}
        
        <div className="glass-panel relative overflow-hidden rounded-3xl p-8 md:p-10">
          <div className="pointer-events-none absolute top-0 right-0 h-64 w-64 translate-x-1/2 -translate-y-1/2 rounded-full bg-teal-200/40 blur-3xl" />
          
          <div className="relative z-10 mb-8 flex items-start justify-between">
            <div>
              <h1 className="mb-2 text-3xl font-bold text-stone-900">Processing Batch #{batchId}</h1>
              <div className="flex items-center gap-2">
                <span className={`flex items-center gap-1 rounded-full border px-3 py-1 text-xs font-bold
                  ${data.status === 'Queued' ? 'border-stone-200 bg-stone-100 text-stone-600' : 
                    data.status === 'In Progress' ? 'border-teal-200 bg-teal-50 text-teal-700' : 
                    data.status === 'Completed' ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 
                    'border-rose-200 bg-rose-50 text-rose-700'}`}
                >
                  {data.status === 'In Progress' && <RefreshCw size={12} className="animate-spin" />}
                  {data.status === 'Completed' && <CheckCircle2 size={12} />}
                  {data.status === 'Queued' && <Loader2 size={12} className="animate-spin" />}
                  {data.status}
                </span>
                <span className="text-sm text-stone-500">{data.valid_rows} rows valid, {data.invalid_rows} invalid</span>
              </div>
            </div>
            
            <div className="text-right">
              <div className="text-4xl font-black text-stone-900">{data.progress}%</div>
            </div>
          </div>

          <div className="relative z-10 space-y-8">
            {/* Progress Bar */}
            <div className="h-4 w-full overflow-hidden rounded-full border border-stone-200 bg-stone-200 shadow-inner">
              <div 
                className={`relative h-full rounded-full transition-all duration-500 ease-out ${isComplete ? 'bg-emerald-500' : 'bg-gradient-to-r from-teal-600 to-cyan-500'}`}
                style={{ width: `${data.progress}%` }}
              >
                {!isComplete && (
                   <div className="absolute inset-0 animate-pulse rounded-full bg-white/20" />
                )}
              </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <div className="rounded-2xl border border-stone-200 bg-white p-4 text-center shadow-sm">
                <p className="mb-1 text-sm text-stone-400">Expected Checks</p>
                <p className="text-2xl font-bold text-stone-900">{data.total_expected}</p>
              </div>
              <div className="rounded-2xl border border-stone-200 bg-white p-4 text-center shadow-sm">
                <p className="mb-1 text-sm text-stone-400">Completed</p>
                <p className="text-2xl font-bold text-stone-900">{data.completed}</p>
              </div>
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-center shadow-sm">
                <p className="mb-1 text-sm text-emerald-700/70">Successful</p>
                <p className="text-2xl font-bold text-emerald-700">{data.successful_checks}</p>
              </div>
              <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-center shadow-sm">
                <p className="mb-1 text-sm text-amber-700/70">Invalid/Errors</p>
                <p className="text-2xl font-bold text-amber-700">{data.invalid_data + data.errors}</p>
              </div>
            </div>
            
            {isComplete && (
              <div className="animate-fade-in-up mt-8 border-t border-stone-200 pt-6 text-center">
                <p className="mb-4 text-stone-500">Processing is complete!</p>
                <Link to={`/results/${batchId}`} className="btn-primary px-8">
                  View Results Dashboard
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
