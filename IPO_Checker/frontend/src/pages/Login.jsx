import React, { useState } from 'react';
import { Lock, Loader2, Eye, EyeOff } from 'lucide-react';
import api, { apiErrorMessage } from '../lib/api';
import { setToken } from '../lib/auth';

export default function Login() {
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!password) return;

    setLoading(true);
    setError(null);
    try {
      const res = await api.post('/auth/login', { password });
      setToken(res.data.token);
      // Full reload so the app's boot gate re-runs and verifies the fresh
      // token behind the splash screen before showing the dashboard.
      window.location.assign('/');
    } catch (err) {
      setError(apiErrorMessage(err, 'Login failed. Please try again.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-[calc(100vh-4rem)] items-center justify-center overflow-hidden bg-[#f6f5f0] p-6">
      <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-teal-200/40 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-24 -left-24 h-72 w-72 rounded-full bg-amber-200/30 blur-3xl" />

      <div className="glass-panel relative w-full max-w-md overflow-hidden rounded-3xl p-8 md:p-10">
        <div className="pointer-events-none absolute top-0 right-0 h-48 w-48 translate-x-1/2 -translate-y-1/2 rounded-full bg-teal-200/40 blur-3xl" />

        <div className="relative z-10">
          <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl border border-teal-200 bg-teal-50">
            <Lock size={28} className="text-teal-700" />
          </div>
          <h1 className="mb-2 text-2xl font-bold text-stone-900">Sign in</h1>
          <p className="mb-8 text-stone-500">Enter the application password to continue.</p>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="label">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoFocus
                  className="input pr-11"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showPassword}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-stone-400 transition-colors hover:text-stone-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500"
                >
                  {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !password}
              className="btn-primary w-full"
            >
              {loading ? <Loader2 className="animate-spin" size={20} /> : <Lock size={18} />}
              {loading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>

          {error && (
            <div className="mt-6 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
              {error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
