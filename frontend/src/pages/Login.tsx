import { useState } from 'react';

interface LoginProps {
  onLogin: (token: string) => void;
}

export function Login({ onLogin }: LoginProps) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      });
      const data = await res.json();
      if (data.success) {
        if (data.token) {
          localStorage.setItem('bs_auth_token', data.token);
        }
        onLogin(data.token || '');
      } else {
        setError(data.error || '密碼錯誤');
      }
    } catch {
      setError('連線失敗，請稍後再試');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="text-5xl mb-3">🍌</div>
          <h1 className="text-2xl font-bold text-white">蕉幻 Banana Slides</h1>
          <p className="text-gray-400 text-sm mt-1">AI 原生 PPT 生成器</p>
        </div>

        {/* Card */}
        <form
          onSubmit={handleSubmit}
          className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl"
        >
          <h2 className="text-white font-semibold text-lg mb-4">請輸入存取密碼</h2>

          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="密碼"
            autoFocus
            className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-3 text-sm outline-none focus:border-yellow-500 transition-colors mb-3"
          />

          {error && (
            <p className="text-red-400 text-sm mb-3">⚠ {error}</p>
          )}

          <button
            type="submit"
            disabled={loading || !password}
            className="w-full bg-yellow-500 hover:bg-yellow-400 disabled:opacity-50 disabled:cursor-not-allowed text-gray-950 font-bold rounded-lg py-3 text-sm transition-colors"
          >
            {loading ? '驗證中…' : '進入'}
          </button>
        </form>
      </div>
    </div>
  );
}
