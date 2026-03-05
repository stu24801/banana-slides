import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Home } from './pages/Home';
import { History } from './pages/History';
import { OutlineEditor } from './pages/OutlineEditor';
import { DetailEditor } from './pages/DetailEditor';
import { SlidePreview } from './pages/SlidePreview';
import { SettingsPage } from './pages/Settings';
import { Login } from './pages/Login';
import { useProjectStore } from './store/useProjectStore';
import { useToast, GithubLink } from './components/shared';
import apiClient from './api/client';

function App() {
  const { currentProject, syncProject, error, setError } = useProjectStore();
  const { show, ToastContainer } = useToast();

  // ── Auth state ─────────────────────────────────────────────────────────────
  const [authReady, setAuthReady] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [authRequired, setAuthRequired] = useState(false);

  useEffect(() => {
    // 啟動時向後端確認 token 是否有效
    const savedToken = localStorage.getItem('bs_auth_token') || '';
    if (savedToken) {
      apiClient.defaults.headers.common['X-Auth-Token'] = savedToken;
    }
    fetch('/api/auth/status', {
      headers: savedToken ? { 'X-Auth-Token': savedToken } : {},
    })
      .then(r => r.json())
      .then(data => {
        setAuthRequired(data.auth_required);
        if (!data.auth_required || data.valid) {
          setAuthed(true);
        }
      })
      .catch(() => {
        // 無法取得狀態時放行（避免後端還沒起來卡住）
        setAuthed(true);
      })
      .finally(() => setAuthReady(true));
  }, []);

  const handleLogin = (token: string) => {
    if (token) {
      apiClient.defaults.headers.common['X-Auth-Token'] = token;
    }
    setAuthed(true);
  };

  // 恢復專案狀態
  useEffect(() => {
    if (!authed) return;
    const savedProjectId = localStorage.getItem('currentProjectId');
    if (savedProjectId && !currentProject) {
      syncProject();
    }
  }, [authed, currentProject, syncProject]);

  // 顯示全域性錯誤
  useEffect(() => {
    if (error) {
      show({ message: error, type: 'error' });
      setError(null);
    }
  }, [error, setError, show]);

  if (!authReady) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-4xl animate-pulse">🍌</div>
      </div>
    );
  }

  if (authRequired && !authed) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/history" element={<History />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/project/:projectId/outline" element={<OutlineEditor />} />
        <Route path="/project/:projectId/detail" element={<DetailEditor />} />
        <Route path="/project/:projectId/preview" element={<SlidePreview />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <ToastContainer />
      <GithubLink />
    </BrowserRouter>
  );
}

export default App;
