import { useState } from 'react';
import type { FormEvent } from 'react';
import logoWhite from '../../assets/landing/logo-white.png';
import logoOrange from '../../assets/landing/logo-orange.png';
import loginIcon from '../../assets/login/login.svg';
import { ThemeToggle } from '../common/ThemeToggle';
import { useTheme } from '../../hooks/useTheme';
import { loginAsync, registerAsync } from '../../services/dummyAuth';
import './LoginPage.css';

interface LoginPageProps {
  onLogin: () => void;
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const [isDark, toggleTheme] = useTheme();
  const [isRegisterMode, setIsRegisterMode] = useState<boolean>(false);
  const [name, setName] = useState<string>('');
  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [error, setError] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const result = isRegisterMode
        ? await registerAsync(name, email, password)
        : await loginAsync(email, password);
      if (result.ok) {
        onLogin();
      } else {
        setError(result.error || 'Autentikasi gagal.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`login ${isDark ? 'login--dark' : 'login--light'}`}>
      <aside className="login__visual" aria-hidden="true">
        <img className="login__bg-logo" src={isDark ? logoOrange : logoWhite} alt="" />
      </aside>

      <section className="login__panel">
        <ThemeToggle isDark={isDark} onToggle={toggleTheme} />

        <h1 className="login__title">
          {isRegisterMode ? 'Daftar Akun Warga' : 'Masuk ke Akun'}
        </h1>

        <form className="login__form" onSubmit={handleSubmit}>
          {isRegisterMode && (
            <label className="login__field">
              <span className="login__label">Nama Lengkap</span>
              <input
                className="login__input"
                type="text"
                placeholder="Masukkan nama lengkap Anda"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </label>
          )}

          <label className="login__field">
            <span className="login__label">Email</span>
            <input
              className="login__input"
              type="email"
              placeholder="Masukkan email Anda"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>

          <label className="login__field">
            <span className="login__label">Kata Sandi</span>
            <input
              className="login__input"
              type="password"
              placeholder="Masukkan kata sandi Anda"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>

          {error && (
            <p className="login__error" role="alert">
              {error}
            </p>
          )}

          <button type="submit" className="login__submit" disabled={loading}>
            <img src={loginIcon} alt="" width={24} height={24} />
            <span>
              {loading
                ? 'Memproses...'
                : isRegisterMode
                ? 'Daftar & Masuk'
                : 'Masuk'}
            </span>
          </button>
        </form>

        {!isRegisterMode && (
          <div
            style={{
              marginTop: '14px',
              padding: '10px 12px',
              borderRadius: '8px',
              border: '1px dashed rgba(204, 111, 0, 0.45)',
              background: 'rgba(204, 111, 0, 0.08)',
              fontSize: '12px',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
            }}
          >
            <span style={{ fontWeight: 600 }}>Akses Cepat Akun Demo:</span>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() => {
                  setEmail('warga@jagaborneo.id');
                  setPassword('warga123');
                  setError('');
                }}
                style={{
                  padding: '4px 10px',
                  fontSize: '11px',
                  fontWeight: 600,
                  borderRadius: '6px',
                  border: '1px solid #059669',
                  background: 'rgba(16, 185, 129, 0.15)',
                  color: '#059669',
                  cursor: 'pointer',
                }}
              >
                Isi Akun Warga (Pelapor)
              </button>
              <button
                type="button"
                onClick={() => {
                  setEmail('admin@jagaborneo.id');
                  setPassword('admin123');
                  setError('');
                }}
                style={{
                  padding: '4px 10px',
                  fontSize: '11px',
                  fontWeight: 600,
                  borderRadius: '6px',
                  border: '1px solid #CC6F00',
                  background: 'rgba(204, 111, 0, 0.15)',
                  color: '#CC6F00',
                  cursor: 'pointer',
                }}
              >
                Isi Akun Petugas (Verifikator)
              </button>
            </div>
          </div>
        )}

        <p className="login__register">
          {isRegisterMode ? (
            <>
              Sudah punya akun?{' '}
              <a
                href="#masuk"
                onClick={(e) => {
                  e.preventDefault();
                  setIsRegisterMode(false);
                  setError('');
                }}
              >
                Masuk disini
              </a>
            </>
          ) : (
            <>
              Belum punya akun?{' '}
              <a
                href="#daftar"
                onClick={(e) => {
                  e.preventDefault();
                  setIsRegisterMode(true);
                  setError('');
                }}
              >
                Daftar disini
              </a>
            </>
          )}
        </p>
      </section>
    </div>
  );
}

export default LoginPage;

