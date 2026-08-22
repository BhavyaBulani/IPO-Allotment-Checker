import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import ModeSelection from './pages/ModeSelection';
import SingleClientEntry from './pages/SingleClientEntry';
import BulkUpload from './pages/BulkUpload';
import ProgressScreen from './pages/ProgressScreen';
import ResultsDashboard from './pages/ResultsDashboard';
import HistoryScreen from './pages/HistoryScreen';
import Login from './pages/Login';
import CaptchaPrompt from './components/CaptchaPrompt';
import { isAuthenticated } from './lib/auth';

function Protected({ children }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

function App() {
  return (
    <BrowserRouter>
      <CaptchaPrompt />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Protected><ModeSelection /></Protected>} />
        <Route path="/single" element={<Protected><SingleClientEntry /></Protected>} />
        <Route path="/bulk" element={<Protected><BulkUpload /></Protected>} />
        <Route path="/progress/:batchId" element={<Protected><ProgressScreen /></Protected>} />
        <Route path="/results/:batchId" element={<Protected><ResultsDashboard /></Protected>} />
        <Route path="/history" element={<Protected><HistoryScreen /></Protected>} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
