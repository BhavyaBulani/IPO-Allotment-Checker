import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Search, ChevronDown, Trash2, Loader2 } from 'lucide-react';

/**
 * Searchable IPO dropdown (typeahead) with a delete button on every option.
 *
 * - Type to filter by name; matches that start with the query are listed
 *   first, then any other name containing it.
 * - Arrow keys + Enter select; Escape closes; clicking outside closes.
 * - Each row carries a trash button that calls `onDelete` for that IPO.
 */
export default function IpoSelect({ ipos, value, onChange, onDelete, deletingId }) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const containerRef = useRef(null);
  const inputRef = useRef(null);

  const selected = useMemo(
    () => ipos.find((ipo) => String(ipo.id) === String(value)),
    [ipos, value]
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return ipos;
    return ipos
      .filter((ipo) => ipo.name.toLowerCase().includes(q))
      .sort((a, b) => {
        const aStart = a.name.toLowerCase().startsWith(q);
        const bStart = b.name.toLowerCase().startsWith(q);
        if (aStart !== bStart) return aStart ? -1 : 1;
        return a.name.localeCompare(b.name);
      });
  }, [ipos, query]);

  // Reflect an externally-selected IPO in the input text (or clear it when
  // the selection is removed, e.g. after deleting the selected IPO).
  useEffect(() => {
    setQuery(selected ? selected.name : '');
  }, [selected]);

  useEffect(() => {
    setHighlight(0);
  }, [query, open]);

  // Close when the user clicks anywhere outside the component.
  useEffect(() => {
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const choose = (ipo) => {
    onChange(String(ipo.id));
    setQuery(ipo.name);
    setOpen(false);
    inputRef.current?.blur();
  };

  const onKeyDown = (e) => {
    if (!open && (e.key === 'ArrowDown' || e.key === 'Enter')) {
      setOpen(true);
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlight((h) => Math.min(h + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filtered[highlight]) choose(filtered[highlight]);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  return (
    <div ref={containerRef} className="relative">
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onKeyDown={onKeyDown}
          placeholder="Search IPO by name..."
          className="input pl-10"
        />
        <Search size={18} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-stone-400" />
        <ChevronDown
          size={18}
          className={`pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-stone-400 transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </div>

      {open && (
        <div className="absolute z-20 mt-2 max-h-72 w-full overflow-y-auto rounded-xl border border-stone-200 bg-white shadow-xl">
          {filtered.length === 0 ? (
            <div className="px-4 py-6 text-center text-sm text-stone-400">
              No IPOs match "{query}"
            </div>
          ) : (
            filtered.map((ipo, idx) => (
              <div
                key={ipo.id}
                onMouseEnter={() => setHighlight(idx)}
                onClick={() => choose(ipo)}
                className={`flex cursor-pointer items-center justify-between gap-3 border-b border-stone-100 px-4 py-2.5 text-sm transition-colors last:border-0 ${
                  idx === highlight ? 'bg-stone-100' : ''
                } ${String(ipo.id) === String(value) ? 'bg-teal-50' : ''}`}
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-stone-900">{ipo.name}</p>
                  <p className="text-[11px] text-stone-400">{ipo.status}</p>
                </div>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(ipo);
                  }}
                  disabled={deletingId === ipo.id}
                  title="Delete this IPO"
                  className="shrink-0 rounded-lg border border-transparent p-2 text-stone-400 transition-colors hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600 disabled:opacity-50"
                >
                  {deletingId === ipo.id ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Trash2 size={16} />
                  )}
                </button>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
