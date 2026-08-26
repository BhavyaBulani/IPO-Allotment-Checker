import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { User, FileSpreadsheet, ArrowRight, Users } from 'lucide-react';
import ClientUploadModal from '../components/ClientUploadModal';

export default function ModeSelection() {
  const [showClientUpload, setShowClientUpload] = useState(false);

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center p-6 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-slate-800 via-slate-900 to-black">
      <div className="text-center mb-12 space-y-4 animate-fade-in-up">
        <div className="inline-block p-2 px-4 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-sm font-semibold tracking-wider mb-2 backdrop-blur-sm">IPO ALLOTMENT VERIFICATION SYSTEM</div>
        <h1 className="text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-white to-slate-400 tracking-tight">How would you like to check?</h1>
        <p className="text-slate-400 max-w-xl mx-auto text-lg">Select a mode to securely verify IPO allotments for your brokerage clients across multiple registrars.</p>
      </div>

      <div className="grid md:grid-cols-2 gap-8 w-full max-w-4xl">
        <Link to="/single" className="group relative glass-panel rounded-3xl p-8 hover:-translate-y-2 transition-all duration-300 hover:shadow-indigo-500/20 hover:border-indigo-500/30 overflow-hidden flex flex-col items-center text-center">
          <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
          <div className="h-20 w-20 bg-indigo-500/10 rounded-full flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300 border border-indigo-500/20">
            <User size={36} className="text-indigo-400" />
          </div>
          <h2 className="text-2xl font-bold text-white mb-3">Single Client Check</h2>
          <p className="text-slate-400 mb-8 flex-grow">Enter a single PAN or Client Code to instantly verify allotment status across all current IPOs.</p>
          <div className="flex items-center text-indigo-400 font-semibold group-hover:translate-x-1 transition-transform">
            Proceed <ArrowRight size={18} className="ml-2" />
          </div>
        </Link>

        <Link to="/bulk" className="group relative glass-panel rounded-3xl p-8 hover:-translate-y-2 transition-all duration-300 hover:shadow-emerald-500/20 hover:border-emerald-500/30 overflow-hidden flex flex-col items-center text-center">
          <div className="absolute inset-0 bg-gradient-to-bl from-emerald-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
          <div className="h-20 w-20 bg-emerald-500/10 rounded-full flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300 border border-emerald-500/20">
            <FileSpreadsheet size={36} className="text-emerald-400" />
          </div>
          <h2 className="text-2xl font-bold text-white mb-3">Bulk Excel Upload</h2>
          <p className="text-slate-400 mb-8 flex-grow">Upload a .xlsx file of clients to process checks across all current IPOs automatically.</p>
          <div className="flex items-center text-emerald-400 font-semibold group-hover:translate-x-1 transition-transform">
            Proceed <ArrowRight size={18} className="ml-2" />
          </div>
        </Link>
      </div>

      <div className="mt-8 flex flex-wrap justify-center gap-4">
        <button 
          onClick={() => setShowClientUpload(true)} 
          className="inline-flex items-center text-slate-400 hover:text-white transition-colors bg-violet-500/10 hover:bg-violet-500/20 px-6 py-3 rounded-xl border border-violet-500/20 hover:border-violet-500/40"
        >
          <Users size={20} className="mr-2 text-violet-400" />
          Upload Client List
        </button>

        <Link to="/history" className="inline-flex items-center text-slate-400 hover:text-white transition-colors bg-slate-800/50 hover:bg-slate-700/50 px-6 py-3 rounded-xl border border-slate-700">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
          View Run History
        </Link>
      </div>

      <ClientUploadModal isOpen={showClientUpload} onClose={() => setShowClientUpload(false)} />
    </div>
  );
}

