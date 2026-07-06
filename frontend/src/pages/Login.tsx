import { useState } from 'react';

interface LoginProps {
  onLogin: (token: string) => void;
}

export function Login({ onLogin }: LoginProps) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (mode === 'register' && password !== confirm) {
      setError('兩次輸入的密碼不一致');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`/api/auth/${mode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (data.success && data.pending_approval) {
        setMode('login');
        setPassword('');
        setConfirm('');
        setNotice(data.message || '註冊成功，帳號待管理員審核通過後即可登入');
      } else if (data.success) {
        localStorage.setItem('bs_auth_token', data.token);
        localStorage.setItem('bs_username', data.username || username);
        onLogin(data.token);
      } else {
        setError(data.error || (mode === 'login' ? '帳號或密碼錯誤' : '註冊失敗'));
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
          <div className="text-5xl mb-3">✨</div>
          <h1 className="text-2xl font-bold text-white">AI 簡報生成器</h1>
          <p className="text-gray-400 text-sm mt-1">AI 原生 PPT 生成器</p>
        </div>

        {/* Card */}
        <form
          onSubmit={handleSubmit}
          className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl"
        >
          <h2 className="text-white font-semibold text-lg mb-4">
            {mode === 'login' ? '登入帳號' : '註冊新帳號'}
          </h2>

          <input
            type="text"
            value={username}
            onChange={e => setUsername(e.target.value)}
            placeholder="帳號"
            autoFocus
            autoComplete="username"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:border-yellow-500 mb-3"
          />
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="密碼"
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:border-yellow-500 mb-3"
          />
          {mode === 'register' && (
            <input
              type="password"
              value={confirm}
              onChange={e => setConfirm(e.target.value)}
              placeholder="確認密碼"
              autoComplete="new-password"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:border-yellow-500 mb-3"
            />
          )}

          {error && <p className="text-red-400 text-sm mb-3">{error}</p>}
          {notice && <p className="text-emerald-400 text-sm mb-3">{notice}</p>}

          <button
            type="submit"
            disabled={loading || !username || !password}
            className="w-full bg-yellow-500 hover:bg-yellow-400 disabled:opacity-50 disabled:cursor-not-allowed text-gray-900 font-semibold rounded-lg py-2.5 transition-colors"
          >
            {loading ? '處理中…' : mode === 'login' ? '登入' : '註冊並登入'}
          </button>

          <p className="text-gray-400 text-sm mt-4 text-center">
            {mode === 'login' ? (
              <>
                還沒有帳號？{' '}
                <button type="button" className="text-yellow-500 hover:underline"
                  onClick={() => { setMode('register'); setError(''); setNotice(''); }}>
                  註冊
                </button>
              </>
            ) : (
              <>
                已有帳號？{' '}
                <button type="button" className="text-yellow-500 hover:underline"
                  onClick={() => { setMode('login'); setError(''); setNotice(''); }}>
                  返回登入
                </button>
              </>
            )}
          </p>
        </form>
      </div>
    </div>
  );
}
