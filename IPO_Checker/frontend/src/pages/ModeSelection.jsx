import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { User, FileSpreadsheet, ArrowRight, Users, Landmark } from 'lucide-react';
import ClientUploadModal from '../components/ClientUploadModal';
import IpoUploadModal from '../components/IpoUploadModal';

export default function ModeSelection() {
  const [showClientUpload, setShowClientUpload] = useState(false);
  const [showIpoUpload, setShowIpoUpload] = useState(false);

  return (
    <div className="relative min-h-[calc(100vh-4rem)] overflow-hidden bg-[#f6f5f0]">
      <div className="pointer-events-none absolute -right-32 -top-32 h-96 w-96 rounded-full bg-teal-200/40 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-40 -left-24 h-96 w-96 rounded-full bg-amber-200/40 blur-3xl" />

      <div className="relative mx-auto flex max-w-5xl flex-col items-center px-6 py-14">
        <div className="mb-12 space-y-4 text-center animate-fade-in-up">
          <div className="inline-block rounded-full border border-teal-200 bg-teal-50 px-4 py-1.5 text-sm font-semibold tracking-wider text-teal-700">
            IPO ALLOTMENT VERIFICATION SYSTEM
          </div>
          <h1 className="text-5xl font-bold tracking-tight text-stone-900">How would you like to check?</h1>
          <p className="mx-auto max-w-xl text-lg text-stone-600">Select a mode to securely verify IPO allotments for your brokerage clients across multiple registrars.</p>
        </div>

        <div className="grid w-full max-w-4xl gap-8 md:grid-cols-2">
          <Link to="/single" className="group relative glass-panel flex flex-col items-center overflow-hidden rounded-3xl p-8 text-center transition-all duration-300 hover:-translate-y-2 hover:shadow-xl hover:shadow-teal-900/10">
            <div className="absolute inset-0 bg-gradient-to-br from-teal-50 to-transparent opacity-0 transition-opacity duration-500 group-hover:opacity-100" />
            <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-full border border-teal-200 bg-teal-50 transition-transform duration-300 group-hover:scale-110">
              <User size={36} className="text-teal-700" />
            </div>
            <h2 className="mb-3 text-2xl font-bold text-stone-900">Single Client Check</h2>
            <p className="mb-8 flex-grow text-stone-600">Enter a single PAN or Client Code to instantly verify allotment status across all current IPOs.</p>
            <div className="flex items-center font-semibold text-teal-700 transition-transform group-hover:translate-x-1">
              Proceed <ArrowRight size={18} className="ml-2" />
            </div>
          </Link>

          <Link to="/bulk" className="group relative glass-panel flex flex-col items-center overflow-hidden rounded-3xl p-8 text-center transition-all duration-300 hover:-translate-y-2 hover:shadow-xl hover:shadow-amber-900/10">
            <div className="absolute inset-0 bg-gradient-to-bl from-amber-50 to-transparent opacity-0 transition-opacity duration-500 group-hover:opacity-100" />
            <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-full border border-amber-200 bg-amber-50 transition-transform duration-300 group-hover:scale-110">
              <FileSpreadsheet size={36} className="text-amber-700" />
            </div>
            <h2 className="mb-3 text-2xl font-bold text-stone-900">Bulk Excel Upload</h2>
            <p className="mb-8 flex-grow text-stone-600">Upload a .xlsx file of clients to process checks across all current IPOs automatically.</p>
            <div className="flex items-center font-semibold text-amber-700 transition-transform group-hover:translate-x-1">
              Proceed <ArrowRight size={18} className="ml-2" />
            </div>
          </Link>
        </div>

        <div className="mt-10 flex flex-wrap justify-center gap-4">
          <button
            onClick={() => setShowIpoUpload(true)}
            className="inline-flex items-center rounded-xl border border-teal-200 bg-teal-50 px-6 py-3 text-teal-700 transition-colors hover:bg-teal-100"
          >
            <Landmark size={20} className="mr-2 text-teal-700" />
            Upload IPO List
          </button>

          <button
            onClick={() => setShowClientUpload(true)}
            className="inline-flex items-center rounded-xl border border-indigo-200 bg-indigo-50 px-6 py-3 text-indigo-700 transition-colors hover:bg-indigo-100"
          >
            <Users size={20} className="mr-2 text-indigo-600" />
            Upload Client List
          </button>

          <Link to="/history" className="inline-flex items-center rounded-xl border border-stone-200 bg-white px-6 py-3 text-stone-600 transition-colors hover:bg-stone-50">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
            View Run History
          </Link>
        </div>
      </div>

      <ClientUploadModal isOpen={showClientUpload} onClose={() => setShowClientUpload(false)} />
      <IpoUploadModal isOpen={showIpoUpload} onClose={() => setShowIpoUpload(false)} />
    </div>
  );
}
