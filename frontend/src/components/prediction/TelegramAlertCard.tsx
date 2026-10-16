import React, { useState } from 'react';
import { createTelegramSubscription } from '../../services/api';

interface TelegramAlertCardProps {
  lat: number;
  lon: number;
  defaultLabel?: string;
  theme: { cardBg: string; modalBorder: string; accentOrange: string };
}

const RADIUS_OPTIONS = [25, 50, 100, 150];

export const TelegramAlertCard: React.FC<TelegramAlertCardProps> = ({
  lat,
  lon,
  defaultLabel = 'Lokasi saya',
  theme,
}) => {
  const [radius, setRadius] = useState<number>(50);
  const [label, setLabel] = useState<string>(defaultLabel);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [link, setLink] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const botUsername = import.meta.env.VITE_TELEGRAM_BOT_USERNAME as string | undefined;

  const handleCreate = async () => {
    setIsLoading(true);
    setError(null);
    setLink(null);
    try {
      const res = await createTelegramSubscription(lat, lon, radius, label.trim());
      const username = botUsername || res.bot_username;
      if (!username) throw new Error('Username bot Telegram belum dikonfigurasi.');
      setLink(`https://t.me/${username}?start=${res.token}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Gagal membuat link alert Telegram.');
    } finally {
      setIsLoading(false);
    }
  };

  const fieldStyle: React.CSSProperties = {
    height: '34px',
    borderRadius: '6px',
    border: `1px solid ${theme.modalBorder}`,
    padding: '0 8px',
    fontSize: '13px',
    background: 'transparent',
    color: 'inherit',
  };

  return (
    <div
      style={{
        margin: '0 22px 18px',
        padding: '14px 16px',
        borderRadius: '10px',
        border: `1px solid ${theme.modalBorder}`,
        backgroundColor: theme.cardBg,
      }}
    >
      <div style={{ fontSize: '14px', fontWeight: 700, marginBottom: '4px' }}>Alert Telegram</div>
      <div style={{ fontSize: '12px', opacity: 0.8, marginBottom: '10px' }}>
        Terima pesan dari bot jika ada hotspot prediktif level SEDANG atau TINGGI di sekitar lokasi ini. Satu akun Telegram
        bisa memantau beberapa lokasi (maks. 5), tekan tombol lagi untuk menambah lokasi lain.
      </div>

      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '10px' }}>
        <input
          aria-label="Nama lokasi"
          value={label}
          maxLength={60}
          onChange={(e) => setLabel(e.target.value)}
          style={{ ...fieldStyle, flex: 1, minWidth: '140px' }}
        />
        <select
          aria-label="Radius alert"
          value={radius}
          onChange={(e) => setRadius(Number(e.target.value))}
          style={fieldStyle}
        >
          {RADIUS_OPTIONS.map((r) => (
            <option key={r} value={r}>
              Radius {r} km
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={handleCreate}
          disabled={isLoading}
          style={{
            height: '34px',
            padding: '0 14px',
            borderRadius: '6px',
            border: 'none',
            backgroundColor: theme.accentOrange,
            color: '#FFFDFA',
            fontSize: '13px',
            fontWeight: 600,
            cursor: isLoading ? 'default' : 'pointer',
          }}
        >
          {isLoading ? 'Membuat link...' : 'Aktifkan Alert Telegram'}
        </button>
      </div>

      {link && (
        <div style={{ fontSize: '13px' }}>
          Link siap.{' '}
          <a href={link} target="_blank" rel="noreferrer" style={{ color: theme.accentOrange, fontWeight: 600 }}>
            Buka Telegram dan tekan Start
          </a>
        </div>
      )}
      {error && <div style={{ fontSize: '12px', color: '#DC2626' }}>{error}</div>}
    </div>
  );
};

