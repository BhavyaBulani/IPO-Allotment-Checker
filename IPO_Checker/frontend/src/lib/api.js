import axios from 'axios';
import { getToken, clearToken } from './auth';

// In production the SPA is served by Vercel but talks to the FastAPI backend on
// Render directly. Routing through Vercel's /api rewrite imposes a short proxy
// timeout that kills slow registrar checks (Link Intime, etc.) with a network
// error, so the browser calls Render's origin and relies on the backend's CORS
// allowlist instead. Local dev keeps the '/api' prefix via the Vite proxy.
const baseURL =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.PROD ? 'https://ipo-allotment-checker.onrender.com/api' : '/api');

const api = axios.create({
  baseURL,
  // Registrar portals can legitimately take 30-90s, and the first request
  // after Render/Aiven free-tier idle can add a cold-start of up to ~60s.
  // 180s keeps slow-but-valid checks alive instead of surfacing a fake
  // "unexpected error" from an early timeout.
  timeout: 180000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach the bearer token to every request. The admin API key is no longer
// sent from the browser: it lived in the bundle/localStorage and was leaking.
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// On auth failure, drop the token and send the user back to the login screen.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearToken();
      if (window.location.pathname !== '/login') {
        window.location.assign('/login');
      }
    }
    return Promise.reject(error);
  }
);

// Human-readable error text for UI toasts/banners. Axios gives a useful
// `err.response.data.detail` for HTTP errors, but timeouts and CORS/network
// failures arrive with no `response` at all — without this the UI falls back
// to a vague "unexpected error" that hides what actually happened.
export function apiErrorMessage(err, fallback = 'An unexpected error occurred') {
  if (err?.response?.data?.detail) return err.response.data.detail;
  if (err?.code === 'ECONNABORTED') {
    return 'The request timed out. Registrar checks can take up to 3 minutes — please try again.';
  }
  if (err?.message) {
    if (/network error/i.test(err.message)) {
      return 'Cannot reach the backend right now. It may be waking up from idle — please retry in a few seconds.';
    }
    return err.message;
  }
  return fallback;
}

export default api;
