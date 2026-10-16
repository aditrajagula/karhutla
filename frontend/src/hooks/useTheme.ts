import { useCallback, useState } from 'react';

const COOKIE_NAME = 'theme';
const MAX_AGE_SECONDS = 60 * 60 * 24 * 365; // 1 tahun

function readThemeCookie(): boolean {
  const match = document.cookie
    .split('; ')
    .find((row) => row.startsWith(`${COOKIE_NAME}=`));
  return match?.split('=')[1] === 'dark';
}

function writeThemeCookie(isDark: boolean): void {
  document.cookie = `${COOKIE_NAME}=${isDark ? 'dark' : 'light'}; path=/; max-age=${MAX_AGE_SECONDS}; SameSite=Lax`;
}

/** Tema terang/gelap yang disimpan di cookie, dibagi antar halaman. */
export function useTheme(): [boolean, () => void] {
  const [isDark, setIsDark] = useState<boolean>(readThemeCookie);

  const toggle = useCallback(() => {
    setIsDark((prev) => {
      const next = !prev;
      writeThemeCookie(next);
      return next;
    });
  }, []);

  return [isDark, toggle];
}
