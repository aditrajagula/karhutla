// Autentikasi DUMMY hanya untuk pengembangan frontend.
// Kredensial ada di sisi klien dan TIDAK aman; ganti dengan autentikasi backend nanti.

const SESSION_KEY = 'jb_session';

export const DUMMY_ACCOUNT = {
  email: 'admin@jagaborneo.id',
  password: 'admin123',
} as const;

export function login(email: string, password: string): boolean {
  const ok =
    email.trim().toLowerCase() === DUMMY_ACCOUNT.email && password === DUMMY_ACCOUNT.password;
  if (ok) sessionStorage.setItem(SESSION_KEY, email.trim().toLowerCase());
  return ok;
}

export function logout(): void {
  sessionStorage.removeItem(SESSION_KEY);
}

export function isLoggedIn(): boolean {
  return sessionStorage.getItem(SESSION_KEY) !== null;
}
