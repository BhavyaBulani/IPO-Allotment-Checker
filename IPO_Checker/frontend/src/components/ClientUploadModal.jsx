import React, { useState, useCallback } from 'react';
import { UploadCloud, FileSpreadsheet, X, Loader2, CheckCircle2, AlertCircle, Users } from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import api from '../lib/api';
import clsx from 'clsx';

export default function ClientUploadModal({ isOpen, onClose }) {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const onDrop = useCallback(acceptedFiles => {
    if (acceptedFiles.length > 0) {
      setFile(acceptedFiles[0]);
      setError(null);
      setResult(null);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ 
    onDrop,
    accept: {
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls']
    },
    maxFiles: 1
  });

  const handleUpload = async () => {
    if (!file) return;

    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await api.post('/clients/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to import client list.");
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setFile(null);
    setResult(null);
    setError(null);
    setLoading(false);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex animate-fade-in items-center justify-center bg-stone-900/40 p-4 backdrop-blur-sm">
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-3xl border border-stone-200 bg-white shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-stone-200 bg-stone-50 p-6">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-violet-100 p-2">
              <Users className="text-violet-700" size={24} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-stone-900">Upload Client List</h2>
              <p className="text-sm text-stone-500">Import clients from Excel (Name, PAN, Client Code)</p>
            </div>
          </div>
          <button 
            onClick={handleClose}
            className="rounded-full p-2 text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-700"
          >
            <X size={20} />
          </button>
        </div>
        
        {/* Body */}
        <div className="flex-grow space-y-6 overflow-y-auto p-6">
          {/* Format hint */}
          <div className="rounded-xl border border-stone-200 bg-stone-50 p-4">
            <h4 className="mb-2 text-sm font-semibold text-stone-700">Expected Excel Format</h4>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-stone-200">
                    <th className="px-3 py-2 text-left font-medium text-stone-400">Name</th>
                    <th className="px-3 py-2 text-left font-medium text-stone-400">PAN</th>
                    <th className="px-3 py-2 text-left font-medium text-stone-400">Client Code</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="text-stone-500">
                    <td className="px-3 py-1.5">Rahul Sharma</td>
                    <td className="px-3 py-1.5 font-mono">ABCDE1234F</td>
                    <td className="px-3 py-1.5 font-mono">RC12345</td>
                  </tr>
                  <tr className="text-stone-500">
                    <td className="px-3 py-1.5">Priya Patel</td>
                    <td className="px-3 py-1.5 font-mono">XYZAB5678G</td>
                    <td className="px-3 py-1.5 font-mono">PP98765</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-[11px] text-stone-400">At least one of PAN or Client Code is required per row. Existing clients will be updated.</p>
          </div>

          {/* Dropzone */}
          {!file ? (
            <div 
              {...getRootProps()} 
              className={clsx(
                "group flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed p-10 text-center transition-all duration-200",
                isDragActive ? "border-violet-400 bg-violet-50" : "border-stone-300 hover:border-stone-400 hover:bg-stone-50"
              )}
            >
              <input {...getInputProps()} />
              <div className={clsx("rounded-full bg-stone-100 p-3 transition-colors group-hover:bg-stone-50", isDragActive && "bg-violet-100")}>
                <UploadCloud size={32} className={clsx("transition-colors", isDragActive ? "text-violet-600" : "text-stone-400 group-hover:text-stone-600")} />
              </div>
              <div>
                <p className="mb-1 font-medium text-stone-800">
                  {isDragActive ? "Drop file here..." : "Drag & drop your client Excel file"}
                </p>
                <p className="text-sm text-stone-400">or click to browse (max 10,000 rows)</p>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between rounded-xl border border-stone-200 bg-white p-5 shadow-sm">
              <div className="flex items-center gap-4">
                <div className="rounded-lg bg-violet-100 p-3 text-violet-700">
                  <FileSpreadsheet size={24} />
                </div>
                <div>
                  <h4 className="font-medium text-stone-900">{file.name}</h4>
                  <p className="text-sm text-stone-400">{(file.size / 1024).toFixed(2)} KB</p>
                </div>
              </div>
              <button onClick={() => { setFile(null); setResult(null); setError(null); }} className="rounded-full p-2 text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-700" title="Remove file">
                <X size={18} />
              </button>
            </div>
          )}

          {/* Upload button */}
          {!result && (
            <button 
              onClick={handleUpload}
              disabled={loading || !file}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-violet-700 py-3.5 font-semibold text-white shadow-sm transition-colors hover:bg-violet-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? <Loader2 className="animate-spin" size={20} /> : <UploadCloud size={20} />}
              {loading ? 'Importing Clients...' : 'Import Client List'}
            </button>
          )}

          {/* Error */}
          {error && (
            <div className="flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-rose-700">
              <AlertCircle className="mt-0.5 shrink-0" size={20} />
              <div>
                <h4 className="mb-1 font-bold text-rose-800">Import Failed</h4>
                <p className="text-sm">{error}</p>
              </div>
            </div>
          )}

          {/* Success Result */}
          {result && (
            <div className="animate-fade-in-up space-y-4">
              <div className="flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-5">
                <CheckCircle2 className="mt-0.5 shrink-0 text-emerald-600" size={22} />
                <div>
                  <h4 className="mb-1 font-bold text-emerald-800">Import Successful</h4>
                  <p className="text-sm text-emerald-700/80">{result.message}</p>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-center">
                  <p className="text-2xl font-bold text-emerald-700">{result.created}</p>
                  <p className="mt-1 text-xs text-emerald-700/60">Created</p>
                </div>
                <div className="rounded-xl border border-violet-200 bg-violet-50 p-4 text-center">
                  <p className="text-2xl font-bold text-violet-700">{result.updated}</p>
                  <p className="mt-1 text-xs text-violet-700/60">Updated</p>
                </div>
                <div className="rounded-xl border border-stone-200 bg-stone-50 p-4 text-center">
                  <p className="text-2xl font-bold text-stone-600">{result.skipped}</p>
                  <p className="mt-1 text-xs text-stone-500">Skipped</p>
                </div>
              </div>

              {result.errors && result.errors.length > 0 && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                  <h4 className="mb-2 text-sm font-semibold text-amber-800">Warnings ({result.errors.length})</h4>
                  <ul className="space-y-1 text-xs text-amber-700/70">
                    {result.errors.map((err, i) => (
                      <li key={i}>• {err}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-stone-200 bg-stone-50 p-6 text-right">
          <button 
            onClick={handleClose}
            className="btn-secondary"
          >
            {result ? 'Done' : 'Cancel'}
          </button>
        </div>
      </div>
    </div>
  );
}
