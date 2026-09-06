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
  // Registrar portals can legitimately take 30-90s; keep the request alive
  // instead of letting it fail at a proxy/browser default.
  timeout: 120000,
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

export default api;
