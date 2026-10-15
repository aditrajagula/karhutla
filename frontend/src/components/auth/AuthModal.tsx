import { useState } from 'react';
import type { FormEvent } from 'react';
import type { AuthUser } from '../../services/api';
import { loginAccount, registerAccount } from '../../services/api';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAuthenticated: (user: AuthUser) => void;
  initialMode?: 'login' | 'register';
}

export function AuthModal({
  isOpen,
  onClose,
  onAuthenticated,
  initialMode = 'login',
}: AuthModalProps) {
  const [mode, setMode] = useState<'login' | 'register'>(initialMode);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<'warga' | 'petugas'>('warga');
  const [institutionCode, setInstitutionCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (mode === 'register') {
        await registerAccount({
          username,
          email: email || undefined,
          password,
          role,
          institution_code: role === 'petugas' ? institutionCode : undefined,
        });
      }
      const session = await loginAccount(mode === 'login' ? username : username, password);
      onAuthenticated(session.user);
      onClose();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Autentikasi gagal.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-modal-title"
      onClick={(event) => {
        if (event.target === event.currentTarget && !loading) onClose();
      }}
    >
      <div className="modal-card" style={{ maxWidth: '440px' }}>
        <div className="modal-header">
          <h2 id="auth-modal-title" className="modal-title">
            {mode === 'login' ? 'Masuk ke FireGuard' : 'Buat Akun FireGuard'}
          </h2>
          <button type="button" className="modal-close-btn" onClick={onClose} disabled={loading} aria-label="Tutup">
            ✕
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body" style={{ display: 'grid', gap: '12px' }}>
            {error && <div role="alert" className="error-banner">{error}</div>}
            <label className="filter-group">
              <span className="filter-label">{mode === 'login' ? 'Username atau email' : 'Username'}</span>
              <input
                autoComplete="username"
                className="filter-input"
                minLength={3}
                maxLength={32}
                required
                value={username}
                onChange={(event) => setUsername(event.target.value)}
              />
            </label>
            {mode === 'register' && (
              <>
                <label className="filter-group">
                  <span className="filter-label">Email (opsional)</span>
                  <input
                    autoComplete="email"
                    className="filter-input"
                    type="email"
                    maxLength={254}
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                  />
                </label>
                <label className="filter-group">
                  <span className="filter-label">Daftar sebagai</span>
                  <select
                    className="filter-input"
                    value={role}
                    onChange={(event) => setRole(event.target.value as 'warga' | 'petugas')}
                  >
                    <option value="warga">Warga</option>
                    <option value="petugas">Petugas (memerlukan kode instansi)</option>
                  </select>
                </label>
                {role === 'petugas' && (
                  <label className="filter-group">
                    <span className="filter-label">Kode instansi</span>
                    <input
                      autoComplete="off"
                      className="filter-input"
                      type="password"
                      required
                      value={institutionCode}
                      onChange={(event) => setInstitutionCode(event.target.value)}
                    />
                  </label>
                )}
              </>
            )}
            <label className="filter-group">
              <span className="filter-label">Password</span>
              <input
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                className="filter-input"
                type="password"
                minLength={mode === 'register' ? 10 : 1}
                maxLength={128}
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              {mode === 'register' && (
                <span style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>
                  Minimal 10 karakter. Password disimpan menggunakan Argon2.
                </span>
              )}
            </label>
            <p className="disclaimer-text">
              Login diperlukan untuk membuat dan memvalidasi laporan. Data laporan merupakan indikasi warga, bukan konfirmasi kejadian.
            </p>
          </div>
          <div className="modal-footer" style={{ display: 'flex', justifyContent: 'space-between', gap: '8px' }}>
            <button
              type="button"
              className="btn-action"
              disabled={loading}
              onClick={() => {
                setMode(mode === 'login' ? 'register' : 'login');
                setError(null);
              }}
            >
              {mode === 'login' ? 'Buat akun' : 'Sudah punya akun? Masuk'}
            </button>
            <button type="submit" className="btn-action" disabled={loading}>
              {loading ? 'Memproses...' : mode === 'login' ? 'Masuk' : 'Daftar & Masuk'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
