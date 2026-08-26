import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Search, Loader2 } from 'lucide-react';
import api from '../lib/api';

export default function SingleClientEntry() {
  const [identifier, setIdentifier] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleCheck = async (e) => {
    e.preventDefault();
    if (!identifier) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await api.post('/check/all', { identifier });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 p-6">
      <div className="max-w-3xl mx-auto pt-10">
        <Link to="/" className="inline-flex items-center text-slate-400 hover:text-white mb-8 transition-colors">
          <ArrowLeft size={20} className="mr-2" /> Back to Mode Selection
        </Link>

        <div className="glass-panel rounded-3xl p-8 md:p-10 relative">
          <div className="absolute inset-0 overflow-hidden rounded-3xl pointer-events-none">
            <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
          </div>

          <h1 className="text-3xl font-bold text-white mb-2">Single Client Check</h1>
          <p className="text-slate-400 mb-10">Enter a PAN or Client Code to check allotment status across all current IPOs.</p>

          <form onSubmit={handleCheck} className="space-y-6 relative z-10">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">PAN or Client Code</label>
              <input
                type="text"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value.toUpperCase())}
                placeholder="e.g. ABCDE1234F or RC12345"
                className="w-full bg-slate-800/50 border border-slate-700 rounded-xl px-4 py-3 text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all shadow-inner font-mono"
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading || identifier.length < 5}
              className="w-full mt-4 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-3 px-6 rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg shadow-indigo-500/20"
            >
              {loading ? <Loader2 className="animate-spin" size={20} /> : <Search size={20} />}
              {loading ? 'Checking...' : 'Check Status'}
            </button>
          </form>

          {error && (
            <div className="mt-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 flex items-start gap-3">
              <span className="font-semibold">Error:</span> {error}
            </div>
          )}

          {result && (
            <div className="mt-8 p-6 bg-slate-800/80 border border-slate-700 rounded-2xl animate-fade-in-up">
              <h3 className="text-xl font-bold text-white mb-4">Verification Result</h3>
              <div className="space-y-3 text-slate-300">
                <div className="flex justify-between border-b border-slate-700 pb-3">
                  <span className="text-slate-400">Status</span>
                  <span className="text-emerald-400 font-semibold">{result.status.toUpperCase()}</span>
                </div>
                <div className="flex justify-between border-b border-slate-700 pb-3">
                  <span className="text-slate-400">Message</span>
                  <span>{result.message}</span>
                </div>
                <div className="flex justify-between border-b border-slate-700 pb-3">
                  <span className="text-slate-400">Detected Format</span>
                  <span className="bg-slate-700 px-2 py-1 rounded text-xs">{result.identifier_type}</span>
                </div>
                {result.results && result.results.length > 0 ? (
                  <div className="mt-4">
                    <span className="text-slate-400 block mb-3 font-semibold">Allotment Details:</span>
                    <div className="space-y-3">
                      {result.results.map((res, idx) => (
                        <div key={idx} className="bg-slate-900/50 p-4 rounded-xl border border-slate-700 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
                          <span className="text-white font-medium">{res.ipo}</span>
                          <div className="text-left sm:text-right">
                            <div className={`text-sm font-bold px-3 py-1 rounded-full inline-block mb-1 ${res.status === 'Allotted' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : res.status === 'Not Allotted' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'}`}>
                              {res.status}
                            </div>
                            <div className="text-xs text-slate-500">{res.message}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div>
                    <span className="text-slate-400 block mb-2">IPOs checked:</span>
                    <div className="flex flex-wrap gap-2">
                      {result.ipos.map((name) => (
                        <span key={name} className="text-xs bg-indigo-500/20 text-indigo-300 px-2 py-1 rounded border border-indigo-500/30">{name}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
