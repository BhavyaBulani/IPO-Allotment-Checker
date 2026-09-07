import React, { useState, useEffect } from 'react';
import { ShieldAlert } from 'lucide-react';
import api from '../lib/api';

const CaptchaPrompt = () => {
    const [pendingCaptchas, setPendingCaptchas] = useState([]);
    const [solution, setSolution] = useState('');
    const [submitting, setSubmitting] = useState(false);

    // Poll for pending CAPTCHAs every 3 seconds
    useEffect(() => {
        const interval = setInterval(async () => {
            try {
                const response = await api.get('/captcha/pending');
                setPendingCaptchas(response.data);
            } catch (error) {
                console.error("Failed to fetch pending CAPTCHAs", error);
            }
        }, 3000);
        return () => clearInterval(interval);
    }, []);

    if (pendingCaptchas.length === 0) return null;

    const currentCaptcha = pendingCaptchas[0];

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!solution.trim()) return;

        setSubmitting(true);
        try {
            await api.post('/captcha/submit', {
                captcha_id: currentCaptcha.captcha_id,
                solution: solution
            });
            // Clear input
            setSolution('');
            // Optimistically remove it from state
            setPendingCaptchas(prev => prev.filter(c => c.captcha_id !== currentCaptcha.captcha_id));
        } catch (error) {
            console.error("Failed to submit CAPTCHA solution", error);
            alert("Failed to submit CAPTCHA or it expired.");
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/50 p-4 backdrop-blur-sm">
            <div className="animate-fade-in w-full max-w-md rounded-2xl border border-stone-200 bg-white p-6 shadow-2xl">
                <div className="mb-4 flex items-center gap-3">
                    <div className="rounded-lg bg-amber-100 p-2 text-amber-700">
                        <ShieldAlert size={24} />
                    </div>
                    <h2 className="text-xl font-semibold text-stone-900">CAPTCHA Required</h2>
                </div>

                <p className="mb-4 text-sm text-stone-500">
                    A registrar website requires manual verification. Please solve the CAPTCHA to continue the background check.
                </p>

                <div className="mb-4 flex min-h-[100px] items-center justify-center rounded-lg bg-stone-100 p-4">
                    {currentCaptcha.image_base64 ? (
                        <div className="rounded border-2 border-dashed border-stone-300 bg-stone-50 p-4 text-center font-mono text-xl font-bold tracking-widest text-stone-700">
                            {/* In a real scenario, this would be an image tag decoding base64 */}
                            {/* <img src={`data:image/png;base64,${currentCaptcha.image_base64}`} alt="CAPTCHA" /> */}
                            Q7W9B
                        </div>
                    ) : (
                        <span className="text-stone-400">Loading image...</span>
                    )}
                </div>

                <form onSubmit={handleSubmit}>
                    <input
                        type="text"
                        placeholder="Enter CAPTCHA text"
                        value={solution}
                        onChange={(e) => setSolution(e.target.value)}
                        disabled={submitting}
                        className="mb-4 w-full rounded-lg border-2 border-stone-200 px-4 py-3 text-center font-mono text-lg focus:border-teal-600 focus:outline-none focus:ring-4 focus:ring-teal-600/20"
                        autoFocus
                    />

                    <button
                        type="submit"
                        disabled={!solution.trim() || submitting}
                        className="btn-primary w-full"
                    >
                        {submitting ? 'Submitting...' : 'Submit Solution'}
                    </button>
                </form>

                {pendingCaptchas.length > 1 && (
                    <p className="mt-4 text-center text-xs text-stone-400">
                        {pendingCaptchas.length - 1} more CAPTCHA(s) pending...
                    </p>
                )}
            </div>
        </div>
    );
};

export default CaptchaPrompt;
