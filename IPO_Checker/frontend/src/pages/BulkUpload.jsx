import React, { useState, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, UploadCloud, FileSpreadsheet, X, Loader2, AlertCircle } from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import api from '../lib/api';
import clsx from 'clsx';

export default function BulkUpload() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const onDrop = useCallback(acceptedFiles => {
    if (acceptedFiles.length > 0) {
      setFile(acceptedFiles[0]);
      setError(null);
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

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await api.post('/check/bulk', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      navigate(`/progress/${res.data.batch_id}`);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to process upload. Please check the file format.");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#f6f5f0] p-6">
      <div className="mx-auto max-w-4xl pt-10">
        <Link to="/" className="back-link mb-8">
          <ArrowLeft size={20} className="mr-2" /> Back to Mode Selection
        </Link>
        
        <div className="glass-panel relative rounded-3xl p-8 md:p-10">
          <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-3xl">
            <div className="absolute top-0 right-0 h-64 w-64 translate-x-1/2 -translate-y-1/2 rounded-full bg-amber-200/40 blur-3xl" />
          </div>
          
          <h1 className="mb-2 text-3xl font-bold text-stone-900">Bulk Excel Upload</h1>
          <p className="mb-10 text-stone-500">Check multiple clients at once by uploading an Excel file.</p>

          <div className="relative z-10 space-y-8">
            <div>
              <label className="label">Upload Client List (.xlsx / .xls)</label>
              {!file ? (
                <div 
                  {...getRootProps()} 
                  className={clsx(
                    "group flex cursor-pointer flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed p-12 text-center transition-all duration-200",
                    isDragActive ? "border-amber-400 bg-amber-50" : "border-stone-300 hover:border-stone-400 hover:bg-white"
                  )}
                >
                  <input {...getInputProps()} />
                  <div className={clsx("rounded-full bg-stone-100 p-4 transition-colors group-hover:bg-stone-50", isDragActive && "bg-amber-100")}>
                    <UploadCloud size={40} className={clsx("transition-colors", isDragActive ? "text-amber-600" : "text-stone-400 group-hover:text-stone-600")} />
                  </div>
                  <div>
                    <p className="mb-1 text-lg font-medium text-stone-800">
                      {isDragActive ? "Drop file here..." : "Drag & drop Excel file here"}
                    </p>
                    <p className="text-sm text-stone-400">or click to browse from your computer (max 10,000 rows)</p>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between rounded-xl border border-stone-200 bg-white p-6 shadow-sm">
                  <div className="flex items-center gap-4">
                    <div className="rounded-lg bg-amber-100 p-3 text-amber-700">
                      <FileSpreadsheet size={28} />
                    </div>
                    <div>
                      <h4 className="font-medium text-stone-900">{file.name}</h4>
                      <p className="text-sm text-stone-400">{(file.size / 1024).toFixed(2)} KB</p>
                    </div>
                  </div>
                  <button onClick={() => setFile(null)} className="rounded-full p-2 text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-700" title="Remove file">
                    <X size={20} />
                  </button>
                </div>
              )}
            </div>

            <button 
              onClick={handleUpload}
              disabled={loading || !file}
              className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-amber-600 py-4 text-lg font-semibold text-white shadow-sm transition-colors hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? <Loader2 className="animate-spin" size={24} /> : <UploadCloud size={24} />}
              {loading ? 'Processing Upload & Validating...' : 'Begin Bulk Verification'}
            </button>
          </div>

          {error && (
            <div className="mt-8 flex items-start gap-4 rounded-2xl border border-rose-200 bg-rose-50 p-5 text-rose-700">
              <AlertCircle className="mt-0.5 shrink-0" />
              <div>
                <h4 className="mb-1 font-bold text-rose-800">Validation Failed</h4>
                <p>{error}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
