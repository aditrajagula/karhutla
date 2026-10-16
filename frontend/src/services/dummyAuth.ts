const SESSION_KEY = 'jb_session';
const TOKEN_KEY = 'jb_token';
const USER_KEY = 'jb_user';

export type UserRole = 'warga' | 'petugas';

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: UserRole;
}

const rawBase = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const cleanBase = rawBase.replace(/\/+$/, '');
const API_BASE_URL = cleanBase.endsWith('/api/v1') ? cleanBase : `${cleanBase}/api/v1`;

export const DUMMY_ACCOUNT = {
  email: 'admin@jagaborneo.id',
  password: 'admin123',
} as const;

const FALLBACK_ACCOUNTS: Array<{ email: string; password: string; user: AuthUser }> = [
  {
    email: 'admin@jagaborneo.id',
    password: 'admin123',
    user: { id: 'usr_admin', email: 'admin@jagaborneo.id', name: 'Petugas Verifikasi JagaBorneo', role: 'petugas' },
  },
  {
    email: 'petugas@jagaborneo.id',
    password: 'petugas123',
    user: { id: 'usr_petugas', email: 'petugas@jagaborneo.id', name: 'Petugas Lapangan', role: 'petugas' },
  },
  {
    email: 'warga@jagaborneo.id',
    password: 'warga123',
    user: { id: 'usr_warga', email: 'warga@jagaborneo.id', name: 'Warga Kalimantan', role: 'warga' },
  },
];

function saveSession(user: AuthUser, token?: string): void {
  sessionStorage.setItem(SESSION_KEY, user.email);
  sessionStorage.setItem(USER_KEY, JSON.stringify(user));
  if (token) {
    sessionStorage.setItem(TOKEN_KEY, token);
  }
}

export function login(email: string, password: string): boolean {
  const cleanEmail = email.trim().toLowerCase();
  const match = FALLBACK_ACCOUNTS.find((a) => a.email === cleanEmail && a.password === password);
  if (match) {
    saveSession(match.user);
    return true;
  }
  return false;
}

export async function loginAsync(
  email: string,
  password: string
): Promise<{ ok: boolean; error?: string; user?: AuthUser }> {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.trim(), password }),
    });
    const data = await res.json();
    if (!res.ok) {
      return { ok: false, error: data?.detail || 'Email atau kata sandi salah.' };
    }
    saveSession(data.user, data.token);
    return { ok: true, user: data.user };
  } catch {
    // Fallback ke akun lokal jika backend sedang tidak terjangkau
    if (login(email, password)) {
      return { ok: true, user: getCurrentUser() || undefined };
    }
    return { ok: false, error: 'Gagal menghubungi server autentikasi.' };
  }
}

export async function registerAsync(
  name: string,
  email: string,
  password: string
): Promise<{ ok: boolean; error?: string; user?: AuthUser }> {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name.trim(), email: email.trim(), password }),
    });
    const data = await res.json();
    if (!res.ok) {
      return { ok: false, error: data?.detail || 'Gagal mendaftarkan akun.' };
    }
    saveSession(data.user, data.token);
    return { ok: true, user: data.user };
  } catch {
    return { ok: false, error: 'Gagal menghubungi server untuk pendaftaran akun.' };
  }
}

export function logout(): void {
  sessionStorage.removeItem(SESSION_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
}

export function isLoggedIn(): boolean {
  return sessionStorage.getItem(SESSION_KEY) !== null;
}

export function getAuthToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function getCurrentUser(): AuthUser | null {
  const raw = sessionStorage.getItem(USER_KEY);
  if (raw) {
    try {
      return JSON.parse(raw) as AuthUser;
    } catch {
      // ignore
    }
  }
  const email = sessionStorage.getItem(SESSION_KEY);
  if (!email) return null;
  const fallback = FALLBACK_ACCOUNTS.find((a) => a.email === email);
  return (
    fallback?.user || {
      id: 'usr_session',
      email,
      name: email.split('@')[0],
      role: email.includes('admin') || email.includes('petugas') ? 'petugas' : 'warga',
    }
  );
}

export function isPetugas(): boolean {
  return getCurrentUser()?.role === 'petugas';
}

