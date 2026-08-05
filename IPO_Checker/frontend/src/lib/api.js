import axios from 'axios';

const adminApiKey = import.meta.env.VITE_ADMIN_API_KEY || localStorage.getItem('admin_api_key');

const api = axios.create({
  baseURL: 'http://localhost:8000/api', // FastAPI default local port
  headers: {
    'Content-Type': 'application/json',
  },
});

if (adminApiKey) {
  api.defaults.headers.common['X-Admin-Key'] = adminApiKey;
}

export default api;
