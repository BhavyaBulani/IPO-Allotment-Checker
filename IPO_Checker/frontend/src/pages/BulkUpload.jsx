import React, { useState, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, UploadCloud, FileSpreadsheet, X, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import IpoMultiSelect from '../components/IpoMultiSelect';
import api from '../lib/api';
import clsx from 'clsx';

export default function BulkUpload() {
  const navigate = useNavigate();
  const [selectedIpos, setSelectedIpos] = useState([]);
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
    if (!file || selectedIpos.length === 0) return;

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('ipo_ids', selectedIpos.map(i => i.id).join(','));

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
    <div className="min-h-screen bg-slate-900 p-6">
      <div className="max-w-4xl mx-auto pt-10">
        <Link to="/" className="inline-flex items-center text-slate-400 hover:text-white mb-8 transition-colors">
          <ArrowLeft size={20} className="mr-2" /> Back to Mode Selection
        </Link>
        
        <div className="glass-panel rounded-3xl p-8 md:p-10 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 pointer-events-none" />
          
          <h1 className="text-3xl font-bold text-white mb-2">Bulk Excel Upload</h1>
          <p className="text-slate-400 mb-10">Check multiple clients at once by uploading an Excel file.</p>

          <div className="space-y-8 relative z-10">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">1. Select Target IPOs</label>
              <IpoMultiSelect selectedIpos={selectedIpos} onChange={setSelectedIpos} />
              {selectedIpos.length > 0 && (
                <p className="text-xs text-indigo-400 mt-2 ml-1 opacity-80">
                  You are scheduling {selectedIpos.length} check(s) per row in the uploaded file.
                </p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">2. Upload Client List (.xlsx / .xls)</label>
              {!file ? (
                <div 
                  {...getRootProps()} 
                  className={clsx(
                    "border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all duration-200 group flex flex-col items-center justify-center gap-4",
                    isDragActive ? "border-emerald-500 bg-emerald-500/10" : "border-slate-700 hover:border-slate-500 hover:bg-slate-800/50"
                  )}
                >
                  <input {...getInputProps()} />
                  <div className={clsx("p-4 rounded-full bg-slate-800 transition-colors group-hover:bg-slate-700", isDragActive && "bg-emerald-500/20")}>
                    <UploadCloud size={40} className={clsx("transition-colors", isDragActive ? "text-emerald-400" : "text-slate-400 group-hover:text-white")} />
                  </div>
                  <div>
                    <p className="text-slate-300 font-medium text-lg mb-1">
                      {isDragActive ? "Drop file here..." : "Drag & drop Excel file here"}
                    </p>
                    <p className="text-slate-500 text-sm">or click to browse from your computer (max 10,000 rows)</p>
                  </div>
                </div>
              ) : (
                <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 flex items-center justify-between shadow-inner">
                  <div className="flex items-center gap-4">
                    <div className="p-3 bg-emerald-500/20 text-emerald-400 rounded-lg">
                      <FileSpreadsheet size={28} />
                    </div>
                    <div>
                      <h4 className="text-white font-medium">{file.name}</h4>
                      <p className="text-slate-400 text-sm">{(file.size / 1024).toFixed(2)} KB</p>
                    </div>
                  </div>
                  <button onClick={() => setFile(null)} className="p-2 hover:bg-slate-700 rounded-full text-slate-400 hover:text-white transition-colors" title="Remove file">
                    <X size={20} />
                  </button>
                </div>
              )}
            </div>

            <button 
              onClick={handleUpload}
              disabled={loading || !file || selectedIpos.length === 0}
              className="w-full mt-4 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-4 px-6 rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20 text-lg"
            >
              {loading ? <Loader2 className="animate-spin" size={24} /> : <UploadCloud size={24} />}
              {loading ? 'Processing Upload & Validating...' : 'Begin Bulk Verification'}
            </button>
          </div>

          {error && (
            <div className="mt-8 p-5 bg-red-500/10 border border-red-500/30 rounded-2xl text-red-400 flex items-start gap-4">
              <AlertCircle className="shrink-0 mt-0.5" />
              <div>
                <h4 className="font-bold text-red-300 mb-1">Validation Failed</h4>
                <p>{error}</p>
              </div>
            </div>
          )}


        </div>
      </div>
    </div>
  );
}
