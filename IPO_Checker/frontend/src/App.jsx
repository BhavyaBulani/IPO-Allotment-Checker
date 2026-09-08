import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import ModeSelection from './pages/ModeSelection';
import SingleClientEntry from './pages/SingleClientEntry';
import BulkUpload from './pages/BulkUpload';
import ProgressScreen from './pages/ProgressScreen';
import ResultsDashboard from './pages/ResultsDashboard';
import HistoryScreen from './pages/HistoryScreen';
import ManageIpos from './pages/ManageIpos';
import Login from './pages/Login';
import CaptchaPrompt from './components/CaptchaPrompt';
import AppHeader from './components/AppHeader';
import SplashScreen from './components/SplashScreen';
import api from './lib/api';
import { getToken, clearToken } from './lib/auth';

// Keep the splash on screen for at least this long so the hand-off into the
// dashboard reads as intentional rather than a flash.
const MIN_SPLASH_MS = 1800;

function Protected({ children }) {
  if (!getToken()) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

function App() {
  // booting -> verifying the stored token behind the splash screen
  // authed  -> token verified, show the app
  // anon    -> no valid token, show the login screen
  const [authState, setAuthState] = useState('booting');
  const [splashStatus, setSplashStatus] = useState('Connecting to markets…');

  useEffect(() => {
    let cancelled = false;
    let attempts = 0;

    const verify = async () => {
      const token = getToken();
      if (!token) {
        setAuthState('anon');
        return;
      }

      const startedAt = Date.now();
      setSplashStatus('Establishing secure session…');

      // Render's free tier sleeps after idle and Aiven's free tier can take a
      // while to wake up, so keep the splash up and retry instead of bouncing
      // to the login page on the first network error.
      while (!cancelled) {
        attempts += 1;
        try {
          await api.get('/auth/verify', { skipAuthRedirect: true });
          if (cancelled) return;

          const elapsed = Date.now() - startedAt;
          if (elapsed < MIN_SPLASH_MS) {
            await new Promise((resolve) => setTimeout(resolve, MIN_SPLASH_MS - elapsed));
          }
          if (!cancelled) setAuthState('authed');
          return;
        } catch (err) {
          if (cancelled) return;

          if (err.response?.status === 401) {
            clearToken();
            setAuthState('anon');
            return;
          }

          setSplashStatus(
            attempts <= 2
              ? 'Warming up the trading desk…'
              : attempts <= 5
              ? 'Loading live market data…'
              : 'Backend is waking from idle — almost there…'
          );
          await new Promise((resolve) =>
            setTimeout(resolve, Math.min(2500 + attempts * 750, 8000))
          );
        }
      }
    };

    verify();

    return () => {
      cancelled = true;
    };
  }, []);

  if (authState === 'booting') {
    return <SplashScreen status={splashStatus} />;
  }

  return (
    <BrowserRouter>
      {authState === 'authed' && <AppHeader />}
      {authState === 'authed' && <CaptchaPrompt />}
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Protected><ModeSelection /></Protected>} />
        <Route path="/single" element={<Protected><SingleClientEntry /></Protected>} />
        <Route path="/bulk" element={<Protected><BulkUpload /></Protected>} />
        <Route path="/progress/:batchId" element={<Protected><ProgressScreen /></Protected>} />
        <Route path="/results/:batchId" element={<Protected><ResultsDashboard /></Protected>} />
        <Route path="/history" element={<Protected><HistoryScreen /></Protected>} />
        <Route path="/manage-ipos" element={<Protected><ManageIpos /></Protected>} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
