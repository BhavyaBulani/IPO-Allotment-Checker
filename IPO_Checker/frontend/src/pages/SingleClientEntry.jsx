import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Search, Loader2, AlertCircle, RefreshCw, ShieldCheck } from 'lucide-react';
import IpoSelect from '../components/IpoSelect';
import api, { apiErrorMessage } from '../lib/api';

// Registrar id for Bigshare Services (see scripts/seed_registrars.py).
const BIGSHARE_REGISTRAR_ID = 3;

export default function SingleClientEntry() {
  const [identifier, setIdentifier] = useState('');
  const [ipos, setIpos] = useState([]);
  const [iposLoading, setIposLoading] = useState(true);
  const [iposError, setIposError] = useState(null);
  const [selectedIpoId, setSelectedIpoId] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  // User-assisted Bigshare CAPTCHA state.
  const [captcha, setCaptcha] = useState(null); // { flow_id, image, ipo }
  const [captchaAnswer, setCaptchaAnswer] = useState('');
  const [captchaRefreshing, setCaptchaRefreshing] = useState(false);
  const [captchaSubmitting, setCaptchaSubmitting] = useState(false);
  const [captchaError, setCaptchaError] = useState(null);

  useEffect(() => {
    const fetchCheckableIpos = async () => {
      setIposLoading(true);
      setIposError(null);
      try {
        const res = await api.get('/ipos/', { params: { checkable: true } });
        setIpos(res.data || []);
      } catch (err) {
        setIposError(err.response?.data?.detail || 'Failed to load available IPOs.');
      } finally {
        setIposLoading(false);
      }
    };
    fetchCheckableIpos();
  }, []);

  const selectedIpo = ipos.find((ipo) => String(ipo.id) === String(selectedIpoId));
  const isBigshare =
    selectedIpo &&
    (selectedIpo.registrar_id === BIGSHARE_REGISTRAR_ID ||
      selectedIpo.registrar_name === 'Bigshare Services');

  const resetCheck = () => {
    setResult(null);
    setError(null);
    setCaptcha(null);
    setCaptchaAnswer('');
    setCaptchaError(null);
  };

  const handleCheck = async (e) => {
    e.preventDefault();
    if (!identifier || !selectedIpoId) return;

    setLoading(true);
    setError(null);
    setResult(null);
    setCaptcha(null);
    setCaptchaAnswer('');
    setCaptchaError(null);

    try {
      if (isBigshare) {
        // Step 1: ask the backend to open a Bigshare session and fetch its CAPTCHA.
        const res = await api.post('/bigshare/captcha', {
          identifier,
          ipo_id: Number(selectedIpoId),
        });
        setCaptcha({ flow_id: res.data.flow_id, image: res.data.image, ipo: res.data.ipo });
      } else {
        const res = await api.post('/check/single', {
          identifier,
          ipo_ids: [Number(selectedIpoId)],
        });
        setResult(res.data);
      }
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleCaptchaRefresh = async () => {
    if (!captcha) return;
    setCaptchaRefreshing(true);
    setCaptchaError(null);
    setCaptchaAnswer('');
    try {
      const res = await api.post('/bigshare/captcha/refresh', { flow_id: captcha.flow_id });
      setCaptcha((prev) => ({ ...prev, image: res.data.image }));
    } catch (err) {
      if (err.response?.status === 410) {
        // Flow expired server-side; restart from scratch.
        setCaptcha(null);
        setError('CAPTCHA session expired. Please start the check again.');
      } else {
        setCaptchaError(apiErrorMessage(err, 'Failed to refresh the CAPTCHA.'));
      }
    } finally {
      setCaptchaRefreshing(false);
    }
  };

  const handleCaptchaSubmit = async (e) => {
    e.preventDefault();
    if (!captcha || !captchaAnswer.trim()) return;

    setCaptchaSubmitting(true);
    setCaptchaError(null);
    try {
      const res = await api.post('/bigshare/check', {
        flow_id: captcha.flow_id,
        captcha_answer: captchaAnswer.trim(),
      });

      if (res.data.captcha_rejected) {
        // Server rejected the answer and returned a fresh image; stay on the
        // CAPTCHA step and let the user retype.
        setCaptcha((prev) => ({ ...prev, image: res.data.image }));
        setCaptchaAnswer('');
        setCaptchaError(res.data.message || 'Invalid CAPTCHA, please try again.');
        return;
      }

      // Success (or a definitive verdict) — show it and clear the CAPTCHA step.
      setResult(res.data);
      setCaptcha(null);
      setCaptchaAnswer('');
    } catch (err) {
      if (err.response?.status === 410) {
        setCaptcha(null);
        setError('CAPTCHA session expired. Please start the check again.');
      } else {
        setCaptchaError(apiErrorMessage(err, 'Failed to submit the CAPTCHA.'));
      }
    } finally {
      setCaptchaSubmitting(false);
    }
  };

  const handleDeleteIpo = async (ipo) => {
    const id = ipo.id;
    if (!window.confirm(
      `Delete IPO "${ipo.name}"?\n\nThis removes it from the dropdown along with its saved check results. You can restore it later by re-uploading the IPO list.`
    )) {
      return;
    }
    setDeletingId(id);
    setError(null);
    try {
      await api.delete(`/ipos/${id}`);
      setIpos((prev) => prev.filter((item) => String(item.id) !== String(id)));
      if (String(selectedIpoId) === String(id)) {
        setSelectedIpoId('');
        resetCheck();
      }
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to delete IPO.'));
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#f6f5f0] p-6">
      <div className="mx-auto max-w-3xl pt-10">
        <Link to="/" className="back-link mb-8">
          <ArrowLeft size={20} className="mr-2" /> Back to Mode Selection
        </Link>

        <div className="glass-panel relative rounded-3xl p-8 md:p-10">
          <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-3xl">
            <div className="absolute top-0 right-0 h-64 w-64 translate-x-1/2 -translate-y-1/2 rounded-full bg-teal-200/40 blur-3xl" />
          </div>

          <h1 className="mb-2 text-3xl font-bold text-stone-900">Single Client Check</h1>
          <p className="mb-10 text-stone-500">Enter a PAN or Client Code and select an IPO to check allotment status.</p>

          <form onSubmit={handleCheck} className="relative z-10 space-y-6">
            <div>
              <label className="label">PAN or Client Code</label>
              <input
                type="text"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value.toUpperCase())}
                placeholder="e.g. ABCDE1234F or RC12345"
                className="input font-mono"
                required
              />
            </div>

            <div>
              <label className="label">Select IPO</label>
              {iposLoading ? (
                <div className="flex w-full items-center gap-2 rounded-xl border border-stone-200 bg-white px-4 py-3 text-stone-400">
                  <Loader2 className="animate-spin" size={16} /> Loading available IPOs...
                </div>
              ) : iposError ? (
                <div className="flex w-full items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                  <AlertCircle size={16} className="mt-0.5 shrink-0" /> {iposError}
                </div>
              ) : ipos.length === 0 ? (
                <div className="w-full rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
                  No IPOs with an announced allotment are available to check right now.
                </div>
              ) : (
                <div className="relative">
                  <IpoSelect
                    ipos={ipos}
                    value={selectedIpoId}
                    onChange={setSelectedIpoId}
                    onDelete={handleDeleteIpo}
                    deletingId={deletingId}
                  />
                  <p className="mt-2 text-xs text-stone-400">Type to search, and use the trash icon to remove an unnecessary IPO.</p>
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={loading || identifier.length < 5 || !selectedIpoId || !!captcha}
              className="btn-primary mt-4 w-full"
            >
              {loading ? <Loader2 className="animate-spin" size={20} /> : <Search size={20} />}
              {loading ? 'Checking...' : 'Check Status'}
            </button>
          </form>

          {/* User-assisted Bigshare CAPTCHA step */}
          {captcha && (
            <div className="relative z-10 mt-8 rounded-2xl border border-stone-200 bg-white p-6 shadow-sm">
              <div className="mb-4 flex items-center gap-3">
                <div className="rounded-lg bg-teal-100 p-2 text-teal-700">
                  <ShieldCheck size={22} />
                </div>
                <div>
                  <h3 className="font-bold text-stone-900">Bigshare CAPTCHA verification</h3>
                  <p className="text-sm text-stone-500">
                    Type the characters shown below to check the status for {captcha.ipo}.
                  </p>
                </div>
              </div>

              <div className="mb-4 flex items-center gap-4">
                <div className="flex min-h-[60px] items-center justify-center rounded-lg border border-stone-200 bg-stone-50 px-2">
                  <img
                    src={captcha.image}
                    alt="Bigshare CAPTCHA"
                    className="max-w-full"
                    style={{ imageRendering: 'pixelated' }}
                  />
                </div>
                <button
                  type="button"
                  onClick={handleCaptchaRefresh}
                  disabled={captchaRefreshing}
                  className="flex items-center gap-2 rounded-lg border border-stone-200 px-3 py-2 text-sm text-stone-600 transition hover:bg-stone-100 disabled:opacity-50"
                  title="Load a new CAPTCHA"
                >
                  <RefreshCw size={16} className={captchaRefreshing ? 'animate-spin' : ''} />
                  Refresh
                </button>
              </div>

              <form onSubmit={handleCaptchaSubmit} className="flex flex-col gap-3 sm:flex-row">
                <input
                  type="text"
                  value={captchaAnswer}
                  onChange={(e) => setCaptchaAnswer(e.target.value.toUpperCase())}
                  placeholder="Enter CAPTCHA text"
                  className="input flex-1 font-mono uppercase"
                  autoComplete="off"
                  autoFocus
                />
                <button
                  type="submit"
                  disabled={!captchaAnswer.trim() || captchaSubmitting}
                  className="btn-primary"
                >
                  {captchaSubmitting ? <Loader2 className="animate-spin" size={20} /> : 'Verify & Check'}
                </button>
              </form>

              {captchaError && (
                <div className="mt-4 flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-rose-700">
                  <span className="font-semibold">CAPTCHA:</span> {captchaError}
                </div>
              )}

              <button
                type="button"
                onClick={resetCheck}
                className="mt-4 text-sm text-stone-400 underline-offset-2 hover:underline"
              >
                Cancel and start over
              </button>
            </div>
          )}

          {error && (
            <div className="relative z-10 mt-6 flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-rose-700">
              <span className="font-semibold">Error:</span> {error}
            </div>
          )}

          {result && (
            <div className="animate-fade-in-up relative z-10 mt-8 rounded-2xl border border-stone-200 bg-white p-6 shadow-sm">
              <h3 className="mb-4 text-xl font-bold text-stone-900">Verification Result</h3>
              <div className="space-y-3 text-stone-600">
                <div className="flex justify-between border-b border-stone-100 pb-3">
                  <span className="text-stone-500">Status</span>
                  <span className="font-semibold text-emerald-700">{result.status.toUpperCase()}</span>
                </div>
                <div className="flex justify-between border-b border-stone-100 pb-3">
                  <span className="text-stone-500">Message</span>
                  <span>{result.message}</span>
                </div>
                <div className="flex justify-between border-b border-stone-100 pb-3">
                  <span className="text-stone-500">Detected Format</span>
                  <span className="rounded bg-stone-100 px-2 py-1 text-xs text-stone-700">{result.identifier_type}</span>
                </div>
                {selectedIpo && (
                  <div className="flex justify-between border-b border-stone-100 pb-3">
                    <span className="text-stone-500">IPO</span>
                    <span className="font-medium text-stone-900">{selectedIpo.name}</span>
                  </div>
                )}
                {result.results && result.results.length > 0 ? (
                  <div className="mt-4">
                    <span className="mb-3 block font-semibold text-stone-500">Allotment Details:</span>
                    <div className="space-y-3">
                      {result.results.map((res, idx) => (
                        <div key={idx} className="flex flex-col items-start justify-between gap-2 rounded-xl border border-stone-200 bg-stone-50 p-4 sm:flex-row sm:items-center">
                          <span className="font-medium text-stone-900">{res.ipo}</span>
                          <div className="text-left sm:text-right">
                            <div className={`mb-1 inline-block rounded-full border px-3 py-1 text-sm font-bold ${res.status === 'Allotted' ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : res.status === 'Not Allotted' ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-amber-200 bg-amber-50 text-amber-700'}`}>
                              {res.status}
                            </div>
                            <div className="text-xs text-stone-500">{res.message}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div>
                    <span className="mb-2 block text-stone-500">IPOs checked:</span>
                    <div className="flex flex-wrap gap-2">
                      {result.ipos.map((name) => (
                        <span key={name} className="rounded border border-teal-200 bg-teal-50 px-2 py-1 text-xs text-teal-700">{name}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
