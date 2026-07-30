import React, { useState, useEffect, useRef } from 'react';
import api from '../lib/api';
import { Check, ChevronsUpDown, X, RefreshCw, Search } from 'lucide-react';
import clsx from 'clsx';

export default function IpoMultiSelect({ selectedIpos, onChange }) {
  const [ipos, setIpos] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('All');
  
  const dropdownRef = useRef(null);
  const inputRef = useRef(null);

  const fetchIpos = () => {
    setLoading(true);
    api.get('/ipos')
      .then(res => {
        setIpos(res.data);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to fetch IPOs", err);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchIpos();
  }, []);

  // Click outside to close
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  // Keyboard navigation (Escape to close)
  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  // Focus input when dropdown opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    } else if (!isOpen) {
      setSearchQuery('');
    }
  }, [isOpen]);

  const handleSync = async (e) => {
    e.stopPropagation();
    setSyncing(true);
    try {
      await api.post('/sync');
      fetchIpos();
    } catch (err) {
      console.error("Failed to sync IPOs", err);
    } finally {
      setSyncing(false);
    }
  };

  const handleSelect = (ipo) => {
    if (selectedIpos.find(i => i.id === ipo.id)) {
      onChange(selectedIpos.filter(i => i.id !== ipo.id));
    } else {
      onChange([...selectedIpos, ipo]);
    }
  };

  const handleRemove = (ipoId, e) => {
    e.stopPropagation();
    onChange(selectedIpos.filter(i => i.id !== ipoId));
  };

  if (loading && ipos.length === 0) return <div className="text-sm text-slate-400 animate-pulse">Loading IPOs...</div>;

  const filteredIpos = ipos.filter(ipo => {
    const matchesSearch = ipo.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = filterStatus === 'All' || ipo.status === filterStatus;
    return matchesSearch && matchesStatus;
  });

  const statuses = ['All', 'Allotment Announced', 'Open', 'Closed'];

  return (
    <div className="relative w-full" ref={dropdownRef}>
      <div className="flex items-center gap-2 mb-2">
        <label className="text-sm font-medium text-slate-300">Select IPOs</label>
        <button 
          type="button"
          onClick={handleSync}
          disabled={syncing}
          className="ml-auto flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 bg-indigo-500/10 hover:bg-indigo-500/20 px-2 py-1 rounded-md transition-colors border border-indigo-500/20 disabled:opacity-50"
        >
          <RefreshCw size={12} className={clsx(syncing && "animate-spin")} />
          {syncing ? 'Syncing...' : 'Sync IPOs'}
        </button>
      </div>
      <div 
        className="min-h-12 w-full p-2 bg-slate-800/50 border border-slate-700 rounded-xl flex items-center justify-between cursor-pointer focus-within:ring-2 focus-within:ring-indigo-500 transition-all shadow-inner"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex flex-wrap gap-2">
          {selectedIpos.length === 0 && <span className="text-slate-400 ml-2">Select IPOs to check...</span>}
          {selectedIpos.map(ipo => (
            <span key={ipo.id} className="inline-flex items-center gap-1 bg-indigo-500/20 text-indigo-300 px-3 py-1 rounded-full text-sm font-medium border border-indigo-500/30 backdrop-blur-sm shadow-sm transition-all hover:bg-indigo-500/30">
              {ipo.name}
              <X size={14} className="cursor-pointer hover:text-white" onClick={(e) => handleRemove(ipo.id, e)} />
            </span>
          ))}
        </div>
        <ChevronsUpDown size={20} className="text-slate-400 mr-2 shrink-0" />
      </div>

      <div 
        className={clsx(
          "absolute z-20 w-full mt-2 bg-slate-800 border border-slate-700 rounded-xl shadow-2xl overflow-hidden transform origin-top transition-all duration-200 ease-out",
          isOpen ? "opacity-100 scale-y-100 pointer-events-auto" : "opacity-0 scale-y-95 pointer-events-none"
        )}
      >
        <div className="p-3 border-b border-slate-700 bg-slate-800/90 backdrop-blur">
          <div className="relative mb-3">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input 
              ref={inputRef}
              type="text"
              placeholder="Search IPOs..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-9 pr-4 py-2 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
            />
          </div>
          <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
            {statuses.map(status => (
              <button
                key={status}
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setFilterStatus(status);
                }}
                className={clsx(
                  "whitespace-nowrap px-3 py-1 text-xs rounded-full font-medium transition-colors border",
                  filterStatus === status 
                    ? "bg-indigo-500/20 text-indigo-300 border-indigo-500/30" 
                    : "bg-slate-900 text-slate-400 border-slate-700 hover:bg-slate-700"
                )}
              >
                {status}
              </button>
            ))}
          </div>
        </div>
        <div className="max-h-60 overflow-y-auto">
          {filteredIpos.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-sm">
              No IPOs found matching your criteria.
            </div>
          ) : (
            filteredIpos.map(ipo => {
              const isSelected = !!selectedIpos.find(i => i.id === ipo.id);
              return (
                <div 
                  key={ipo.id}
                  className={clsx("flex items-center justify-between p-3 hover:bg-slate-700 cursor-pointer transition-colors border-b border-slate-700/50 last:border-0", isSelected && "bg-slate-700/50")}
                  onClick={() => handleSelect(ipo)}
                >
                  <div className="flex flex-col">
                    <span className={clsx("font-medium", isSelected ? "text-indigo-400" : "text-slate-200")}>{ipo.name}</span>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={clsx("text-xs px-2 py-0.5 rounded-md border", 
                        ipo.status === 'Allotment Announced' ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" :
                        ipo.status === 'Open' ? "bg-amber-500/10 text-amber-400 border-amber-500/20" :
                        "bg-slate-900 text-slate-400 border-slate-700"
                      )}>{ipo.status}</span>
                      {ipo.auto_detected && <span className="text-[10px] text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 px-1.5 py-0.5 rounded-sm uppercase tracking-wider font-semibold">Auto-detected</span>}
                    </div>
                  </div>
                  {isSelected && <Check size={18} className="text-indigo-400" />}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
