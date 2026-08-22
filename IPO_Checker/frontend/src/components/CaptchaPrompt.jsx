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
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center">
            <div className="bg-white rounded-xl shadow-2xl p-6 w-full max-w-md animate-in zoom-in-95">
                <div className="flex items-center gap-3 mb-4">
                    <div className="p-2 bg-amber-100 text-amber-600 rounded-lg">
                        <ShieldAlert size={24} />
                    </div>
                    <h2 className="text-xl font-semibold text-gray-800">CAPTCHA Required</h2>
                </div>

                <p className="text-gray-600 mb-4 text-sm">
                    A registrar website requires manual verification. Please solve the CAPTCHA to continue the background check.
                </p>

                <div className="bg-gray-100 rounded-lg p-4 mb-4 flex justify-center items-center min-h-[100px]">
                    {currentCaptcha.image_base64 ? (
                        <div className="text-center font-mono text-xl tracking-widest text-gray-700 font-bold border-2 border-dashed border-gray-300 p-4 rounded bg-gray-50">
                            {/* In a real scenario, this would be an image tag decoding base64 */}
                            {/* <img src={`data:image/png;base64,${currentCaptcha.image_base64}`} alt="CAPTCHA" /> */}
                            Q7W9B
                        </div>
                    ) : (
                        <span className="text-gray-400">Loading image...</span>
                    )}
                </div>

                <form onSubmit={handleSubmit}>
                    <input
                        type="text"
                        placeholder="Enter CAPTCHA text"
                        value={solution}
                        onChange={(e) => setSolution(e.target.value)}
                        disabled={submitting}
                        className="w-full border-2 border-gray-200 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-500/20 transition-all font-mono text-center text-lg mb-4"
                        autoFocus
                    />

                    <button
                        type="submit"
                        disabled={!solution.trim() || submitting}
                        className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {submitting ? 'Submitting...' : 'Submit Solution'}
                    </button>
                </form>

                {pendingCaptchas.length > 1 && (
                    <p className="text-xs text-center text-gray-500 mt-4">
                        {pendingCaptchas.length - 1} more CAPTCHA(s) pending...
                    </p>
                )}
            </div>
        </div>
    );
};

export default CaptchaPrompt;
