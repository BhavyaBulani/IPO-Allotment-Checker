import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Loader2, AlertCircle, Trash2, Landmark, Search, ShieldCheck, ShieldAlert } from 'lucide-react';
import api, { apiErrorMessage } from '../lib/api';

const STATUS_STYLE = {
  'Allotment Announced': 'border-emerald-200 bg-emerald-50 text-emerald-700',
  'Open': 'border-teal-200 bg-teal-50 text-teal-700',
  'Upcoming': 'border-amber-200 bg-amber-50 text-amber-700',
  'Closed': 'border-stone-200 bg-stone-100 text-stone-600',
};

export default function ManageIpos() {
  const [ipos, setIpos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all'); // all | published | held
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(new Set());
  const [deleting, setDeleting] = useState(null);

  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.get('/ipos/admin');
        setIpos(res.data || []);
      } catch (err) {
        setError(apiErrorMessage(err, 'Failed to load IPOs.'));
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, []);

  const filtered = useMemo(() => {
    return ipos.filter((ipo) => {
      if (filter === 'published' && !ipo.validated) return false;
      if (filter === 'held' && ipo.validated) return false;
      if (query && !ipo.name.toLowerCase().includes(query.toLowerCase())) return false;
      return true;
    });
  }, [ipos, filter, query]);

  const toggle = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleAll = () => {
    setSelected((prev) => {
      if (prev.size === filtered.length && filtered.length > 0) return new Set();
      return new Set(filtered.map((i) => i.id));
    });
  };

  const deleteOne = async (ipo) => {
    if (!window.confirm(`Delete IPO "${ipo.name}"?\n\nThis removes it from the dropdown and deletes its saved check results.`)) return;
    setDeleting(ipo.id);
    setError(null);
    try {
      await api.delete(`/ipos/${ipo.id}`);
      setIpos((prev) => prev.filter((i) => i.id !== ipo.id));
      setSelected((prev) => { const n = new Set(prev); n.delete(ipo.id); return n; });
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to delete IPO.'));
    } finally {
      setDeleting(null);
    }
  };

  const deleteSelected = async () => {
    if (selected.size === 0) return;
    if (!window.confirm(`Delete ${selected.size} selected IPO(s)?\n\nThis also deletes their saved check results.`)) return;
    setError(null);
    for (const id of Array.from(selected)) {
      setDeleting(id);
      try {
        await api.delete(`/ipos/${id}`);
      } catch (err) {
        setError(apiErrorMessage(err, `Failed to delete IPO #${id}.`));
        setDeleting(null);
        return;
      }
      setDeleting(null);
    }
    setIpos((prev) => prev.filter((i) => !selected.has(i.id)));
    setSelected(new Set());
  };

  const publishedCount = ipos.filter((i) => i.validated).length;
  const heldCount = ipos.length - publishedCount;

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#f6f5f0] p-6 pb-20">
      <div className="mx-auto max-w-6xl pt-8">
        <Link to="/" className="back-link mb-8">
          <ArrowLeft size={20} className="mr-2" /> Back to Home
        </Link>

        <div className="mb-8 flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <h1 className="mb-2 text-3xl font-bold text-stone-900">Manage IPOs</h1>
            <p className="text-stone-500">View the full catalogue, including held-for-review rows, and delete stale or duplicate entries.</p>
          </div>
          <div className="flex gap-3">
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-700">
              <ShieldCheck size={16} className="mr-1 inline" /> {publishedCount} published
            </div>
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-700">
              <ShieldAlert size={16} className="mr-1 inline" /> {heldCount} held
            </div>
          </div>
        </div>

        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap gap-2">
            {[
              ['all', 'All'],
              ['published', 'Published'],
              ['held', 'Held for review'],
            ].map(([value, label]) => (
              <button
                key={value}
                onClick={() => setFilter(value)}
                className={`rounded-lg border px-4 py-2 text-sm font-medium transition-colors ${
                  filter === value ? 'border-teal-700 bg-teal-700 text-white' : 'border-stone-200 bg-white text-stone-600 hover:bg-stone-50'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="relative w-full sm:w-72">
            <Search size={18} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search IPO by name..."
              className="w-full rounded-lg border border-stone-300 bg-white py-2 pl-10 pr-4 text-stone-800 placeholder:text-stone-400 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20"
            />
          </div>
        </div>

        {error && (
          <div className="mb-4 flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-rose-700">
            <AlertCircle size={18} className="mt-0.5 shrink-0" /> {error}
          </div>
        )}

        <div className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
          <div className="flex items-center justify-between border-b border-stone-200 bg-stone-50 p-4">
            <div className="flex items-center gap-3">
              <button
                onClick={toggleAll}
                disabled={filtered.length === 0}
                className="rounded-lg border border-stone-200 bg-white px-3 py-1.5 text-sm text-stone-600 transition-colors hover:bg-stone-50 disabled:opacity-50"
              >
                {selected.size === filtered.length && filtered.length > 0 ? 'Clear all' : 'Select all'}
              </button>
              <span className="text-sm text-stone-400">{selected.size} selected</span>
            </div>
            <button
              onClick={deleteSelected}
              disabled={selected.size === 0 || deleting !== null}
              className="inline-flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 transition-colors hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Trash2 size={16} /> Delete selected
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-stone-200 bg-stone-50 text-sm text-stone-500">
                  <th className="w-10 px-4 py-3"></th>
                  <th className="px-4 py-3 font-medium">IPO</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Registrar</th>
                  <th className="px-4 py-3 font-medium">Source</th>
                  <th className="px-4 py-3 font-medium">State</th>
                  <th className="px-4 py-3 text-right font-medium">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {loading ? (
                  <tr>
                    <td colSpan="7" className="px-4 py-12 text-center text-stone-400">
                      <Loader2 className="mr-2 inline animate-spin" size={20} /> Loading IPOs...
                    </td>
                  </tr>
                ) : filtered.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="px-4 py-12 text-center text-stone-400">
                      <Landmark size={24} className="mx-auto mb-2" /> No IPOs match this filter.
                    </td>
                  </tr>
                ) : (
                  filtered.map((ipo) => (
                    <tr key={ipo.id} className={`transition-colors hover:bg-stone-50 ${ipo.validated ? '' : 'bg-amber-50/40'}`}>
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={selected.has(ipo.id)}
                          onChange={() => toggle(ipo.id)}
                          className="h-4 w-4 accent-teal-700"
                        />
                      </td>
                      <td className="px-4 py-3">
                        <p className="font-medium text-stone-900">{ipo.name}</p>
                        <p className="text-xs text-stone-400">#{ipo.id}</p>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-block rounded-full border px-3 py-1 text-xs font-bold ${STATUS_STYLE[ipo.status] || 'border-stone-200 bg-stone-100 text-stone-600'}`}>
                          {ipo.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-stone-600">
                        {ipo.registrar_name || <span className="text-amber-600">Not mapped</span>}
                      </td>
                      <td className="px-4 py-3 text-sm text-stone-400">{ipo.source || '—'}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold ${
                          ipo.validated ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-amber-200 bg-amber-50 text-amber-700'
                        }`}>
                          {ipo.validated ? 'Published' : 'Held'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => deleteOne(ipo)}
                          disabled={deleting === ipo.id}
                          title="Delete IPO"
                          className="rounded-lg border border-transparent p-2 text-stone-400 transition-colors hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600 disabled:opacity-50"
                        >
                          {deleting === ipo.id ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
