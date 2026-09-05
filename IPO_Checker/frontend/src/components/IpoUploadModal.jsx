import React, { useState, useCallback } from 'react';
import { UploadCloud, FileSpreadsheet, X, Loader2, CheckCircle2, AlertCircle, Landmark, Download } from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import api from '../lib/api';
import clsx from 'clsx';

export default function IpoUploadModal({ isOpen, onClose }) {
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
      'text/csv': ['.csv'],
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
      const res = await api.post('/ipos/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to import IPO list.");
    } finally {
      setLoading(false);
    }
  };

  const downloadTemplate = () => {
    const header = 'Name,Close Date,Status,Registrar';
    const rows = [
      'ABC Infra Ltd,28-Aug-2026,Closed,Link Intime',
      'XYZ Power Ltd,30-Aug-2026,Allotment Announced,KFin Technologies',
      'LMN Retail Ltd,25-Aug-2026,Closed,Bigshare Services'
    ];
    const csv = [header, ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'ipo_list_template.csv';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleClose = () => {
    setFile(null);
    setResult(null);
    setError(null);
    setLoading(false);
    onClose();
  };

  if (!isOpen) return null;

  const warnings = [
    ...(result?.unmapped_registrars || []),
    ...(result?.errors || [])
  ];

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fade-in-up">
      <div className="bg-slate-900 border border-slate-700 rounded-3xl w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="p-6 border-b border-slate-800 flex justify-between items-center bg-slate-800/50">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/20 rounded-lg">
              <Landmark className="text-emerald-400" size={24} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Upload IPO List</h2>
              <p className="text-slate-400 text-sm">Import closed IPOs from CSV / Excel (Name, Close Date, Registrar)</p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="text-slate-400 hover:text-white p-2 rounded-full hover:bg-slate-800 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto flex-grow space-y-6">
          {/* Format hint */}
          <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-semibold text-slate-300">Expected File Format</h4>
              <button
                onClick={downloadTemplate}
                className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-400 hover:text-emerald-300 bg-emerald-500/10 hover:bg-emerald-500/20 px-3 py-1.5 rounded-lg border border-emerald-500/20 transition-colors"
              >
                <Download size={14} />
                Download CSV template
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="text-xs w-full">
                <thead>
                  <tr className="border-b border-slate-700">
                    <th className="text-left py-2 px-3 text-slate-400 font-medium">Name</th>
                    <th className="text-left py-2 px-3 text-slate-400 font-medium">Close Date</th>
                    <th className="text-left py-2 px-3 text-slate-400 font-medium">Status</th>
                    <th className="text-left py-2 px-3 text-slate-400 font-medium">Registrar</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="text-slate-500">
                    <td className="py-1.5 px-3">ABC Infra Ltd</td>
                    <td className="py-1.5 px-3">28-Aug-2026</td>
                    <td className="py-1.5 px-3">Closed</td>
                    <td className="py-1.5 px-3">Link Intime</td>
                  </tr>
                  <tr className="text-slate-500">
                    <td className="py-1.5 px-3">XYZ Power Ltd</td>
                    <td className="py-1.5 px-3">30-Aug-2026</td>
                    <td className="py-1.5 px-3">Allotment Announced</td>
                    <td className="py-1.5 px-3">KFin Technologies</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="text-[11px] text-slate-500 mt-2">
              Only <span className="text-slate-300">Name</span> is required. Status defaults to <span className="text-slate-300">Closed</span>.
              Registrar is strongly recommended so each IPO routes to the correct registrar. Columns can be in any order.
            </p>
          </div>

          {/* Dropzone */}
          {!file ? (
            <div
              {...getRootProps()}
              className={clsx(
                "border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all duration-200 group flex flex-col items-center justify-center gap-3",
                isDragActive ? "border-emerald-500 bg-emerald-500/10" : "border-slate-700 hover:border-slate-500 hover:bg-slate-800/50"
              )}
            >
              <input {...getInputProps()} />
              <div className={clsx("p-3 rounded-full bg-slate-800 transition-colors group-hover:bg-slate-700", isDragActive && "bg-emerald-500/20")}>
                <UploadCloud size={32} className={clsx("transition-colors", isDragActive ? "text-emerald-400" : "text-slate-400 group-hover:text-white")} />
              </div>
              <div>
                <p className="text-slate-300 font-medium mb-1">
                  {isDragActive ? "Drop file here..." : "Drag & drop your IPO CSV/Excel file"}
                </p>
                <p className="text-slate-500 text-sm">or click to browse (.csv / .xlsx / .xls, max 10,000 rows)</p>
              </div>
            </div>
          ) : (
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 flex items-center justify-between shadow-inner">
              <div className="flex items-center gap-4">
                <div className="p-3 bg-emerald-500/20 text-emerald-400 rounded-lg">
                  <FileSpreadsheet size={24} />
                </div>
                <div>
                  <h4 className="text-white font-medium">{file.name}</h4>
                  <p className="text-slate-400 text-sm">{(file.size / 1024).toFixed(2)} KB</p>
                </div>
              </div>
              <button onClick={() => { setFile(null); setResult(null); setError(null); }} className="p-2 hover:bg-slate-700 rounded-full text-slate-400 hover:text-white transition-colors" title="Remove file">
                <X size={18} />
              </button>
            </div>
          )}

          {/* Upload button */}
          {!result && (
            <button
              onClick={handleUpload}
              disabled={loading || !file}
              className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-3.5 px-6 rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20"
            >
              {loading ? <Loader2 className="animate-spin" size={20} /> : <UploadCloud size={20} />}
              {loading ? 'Importing IPOs...' : 'Import IPO List'}
            </button>
          )}

          {/* Error */}
          {error && (
            <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 flex items-start gap-3">
              <AlertCircle className="shrink-0 mt-0.5" size={20} />
              <div>
                <h4 className="font-bold text-red-300 mb-1">Import Failed</h4>
                <p className="text-sm">{error}</p>
              </div>
            </div>
          )}

          {/* Success Result */}
          {result && (
            <div className="animate-fade-in-up space-y-4">
              <div className="p-5 bg-emerald-500/10 border border-emerald-500/30 rounded-xl flex items-start gap-3">
                <CheckCircle2 className="shrink-0 mt-0.5 text-emerald-400" size={22} />
                <div>
                  <h4 className="font-bold text-emerald-300 mb-1">Import Successful</h4>
                  <p className="text-emerald-400/80 text-sm">{result.message}</p>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="bg-emerald-500/10 p-4 rounded-xl border border-emerald-500/20 text-center">
                  <p className="text-emerald-400 text-2xl font-bold">{result.created}</p>
                  <p className="text-emerald-400/60 text-xs mt-1">Created</p>
                </div>
                <div className="bg-indigo-500/10 p-4 rounded-xl border border-indigo-500/20 text-center">
                  <p className="text-indigo-400 text-2xl font-bold">{result.updated}</p>
                  <p className="text-indigo-400/60 text-xs mt-1">Updated</p>
                </div>
                <div className="bg-slate-500/10 p-4 rounded-xl border border-slate-600 text-center">
                  <p className="text-slate-300 text-2xl font-bold">{result.skipped}</p>
                  <p className="text-slate-400/60 text-xs mt-1">Skipped</p>
                </div>
              </div>

              {warnings.length > 0 && (
                <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl">
                  <h4 className="text-amber-300 font-semibold text-sm mb-2">Warnings ({warnings.length})</h4>
                  <ul className="text-amber-400/70 text-xs space-y-1">
                    {warnings.map((w, i) => (
                      <li key={i}>• {w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-slate-800 bg-slate-900/50 text-right">
          <button
            onClick={handleClose}
            className="bg-slate-700 hover:bg-slate-600 text-white font-semibold py-2.5 px-6 rounded-xl transition-colors"
          >
            {result ? 'Done' : 'Cancel'}
          </button>
        </div>
      </div>
    </div>
  );
}
