import { BrowserRouter, Routes, Route } from 'react-router-dom';
import ModeSelection from './pages/ModeSelection';
import SingleClientEntry from './pages/SingleClientEntry';
import BulkUpload from './pages/BulkUpload';
import ProgressScreen from './pages/ProgressScreen';
import ResultsDashboard from './pages/ResultsDashboard';
import HistoryScreen from './pages/HistoryScreen';
import CaptchaPrompt from './components/CaptchaPrompt';

function App() {
  return (
    <BrowserRouter>
      <CaptchaPrompt />
      <Routes>
        <Route path="/" element={<ModeSelection />} />
        <Route path="/single" element={<SingleClientEntry />} />
        <Route path="/bulk" element={<BulkUpload />} />
        <Route path="/progress/:batchId" element={<ProgressScreen />} />
        <Route path="/results/:batchId" element={<ResultsDashboard />} />
        <Route path="/history" element={<HistoryScreen />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
