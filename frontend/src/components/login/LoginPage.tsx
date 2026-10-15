import { useState } from 'react';
import type { FormEvent } from 'react';
import logoWhite from '../../assets/landing/logo-white.png';
import logoOrange from '../../assets/landing/logo-orange.png';
import loginIcon from '../../assets/login/login.svg';
import { ThemeToggle } from '../common/ThemeToggle';
import { useTheme } from '../../hooks/useTheme';
import './LoginPage.css';

interface LoginPageProps {
  onLogin: () => void;
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const [isDark, toggleTheme] = useTheme();
  const [email, setEmail] = useState<string>('');
  const [password, setPassword] = useState<string>('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    // TODO: hubungkan ke endpoint autentikasi backend
    onLogin();
  };

  return (
    <div className={`login ${isDark ? 'login--dark' : 'login--light'}`}>
      <aside className="login__visual" aria-hidden="true">
        <img className="login__bg-logo" src={isDark ? logoOrange : logoWhite} alt="" />
      </aside>

      <section className="login__panel">
        <ThemeToggle isDark={isDark} onToggle={toggleTheme} />

        <h1 className="login__title">Masuk ke Akun</h1>

        <form className="login__form" onSubmit={handleSubmit}>
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

          <button type="submit" className="login__submit">
            <img src={loginIcon} alt="" width={24} height={24} />
            <span>Masuk</span>
          </button>
        </form>

        <p className="login__register">
          Belum punya akun? <a href="#daftar">Daftar disini</a>
        </p>
      </section>
    </div>
  );
}

export default LoginPage;
