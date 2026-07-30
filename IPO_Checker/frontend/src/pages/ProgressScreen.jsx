import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Loader2, CheckCircle2, AlertCircle, PlayCircle, StopCircle, RefreshCw } from 'lucide-react';
import api from '../lib/api';

export default function ProgressScreen() {
  const { batchId } = useParams();
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
      <div className="min-h-screen bg-slate-900 p-6 flex items-center justify-center">
        <div className="bg-red-500/10 p-6 rounded-2xl border border-red-500/30 text-red-400 flex items-center gap-4">
          <AlertCircle size={32} />
          <div>
            <h3 className="font-bold text-lg mb-1">Error</h3>
            <p>{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-slate-900 p-6 flex items-center justify-center text-slate-400">
        <Loader2 className="animate-spin mr-3" size={24} /> Loading batch {batchId}...
      </div>
    );
  }

  const isComplete = data.status === 'Completed';

  return (
    <div className="min-h-screen bg-slate-900 p-6">
      <div className="max-w-3xl mx-auto pt-10">
        <Link to="/" className="inline-flex items-center text-slate-400 hover:text-white mb-8 transition-colors">
          <ArrowLeft size={20} className="mr-2" /> Back to Home
        </Link>
        
        <div className="glass-panel rounded-3xl p-8 md:p-10 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 pointer-events-none" />
          
          <div className="flex justify-between items-start mb-8 relative z-10">
            <div>
              <h1 className="text-3xl font-bold text-white mb-2">Processing Batch #{batchId}</h1>
              <div className="flex items-center gap-2">
                <span className={`px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1
                  ${data.status === 'Queued' ? 'bg-slate-700 text-slate-300' : 
                    data.status === 'In Progress' ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30' : 
                    data.status === 'Completed' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 
                    'bg-red-500/20 text-red-400 border border-red-500/30'}`}
                >
                  {data.status === 'In Progress' && <RefreshCw size={12} className="animate-spin" />}
                  {data.status === 'Completed' && <CheckCircle2 size={12} />}
                  {data.status === 'Queued' && <Loader2 size={12} className="animate-spin" />}
                  {data.status}
                </span>
                <span className="text-slate-500 text-sm">{data.valid_rows} rows valid, {data.invalid_rows} invalid</span>
              </div>
            </div>
            
            <div className="text-right">
              <div className="text-4xl font-black text-white">{data.progress}%</div>
            </div>
          </div>

          <div className="space-y-8 relative z-10">
            {/* Progress Bar */}
            <div className="w-full bg-slate-800 rounded-full h-4 overflow-hidden border border-slate-700 shadow-inner">
              <div 
                className={`h-full rounded-full transition-all duration-500 ease-out ${isComplete ? 'bg-emerald-500' : 'bg-gradient-to-r from-indigo-500 to-cyan-400 relative'}`}
                style={{ width: `${data.progress}%` }}
              >
                {!isComplete && (
                   <div className="absolute inset-0 bg-white/20 animate-pulse rounded-full" />
                )}
              </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-slate-800/50 p-4 rounded-2xl border border-slate-700 text-center shadow-sm">
                <p className="text-slate-400 text-sm mb-1">Expected Checks</p>
                <p className="text-white text-2xl font-bold">{data.total_expected}</p>
              </div>
              <div className="bg-slate-800/50 p-4 rounded-2xl border border-slate-700 text-center shadow-sm">
                <p className="text-slate-400 text-sm mb-1">Completed</p>
                <p className="text-white text-2xl font-bold">{data.completed}</p>
              </div>
              <div className="bg-emerald-500/5 p-4 rounded-2xl border border-emerald-500/20 text-center shadow-sm">
                <p className="text-emerald-400/80 text-sm mb-1">Successful</p>
                <p className="text-emerald-400 text-2xl font-bold">{data.successful_checks}</p>
              </div>
              <div className="bg-amber-500/5 p-4 rounded-2xl border border-amber-500/20 text-center shadow-sm">
                <p className="text-amber-400/80 text-sm mb-1">Invalid/Errors</p>
                <p className="text-amber-400 text-2xl font-bold">{data.invalid_data + data.errors}</p>
              </div>
            </div>
            
            {isComplete && (
              <div className="mt-8 pt-6 border-t border-slate-700 text-center animate-fade-in-up">
                <p className="text-slate-400 mb-4">Processing is complete!</p>
                <Link to={`/results/${batchId}`} className="inline-block bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-3 px-8 rounded-xl transition-all shadow-lg shadow-indigo-500/20">
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
