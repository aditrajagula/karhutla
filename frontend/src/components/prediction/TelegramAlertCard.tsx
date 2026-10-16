import React, { useState } from 'react';
import { createTelegramSubscription } from '../../services/api';
import { SendIcon, ClockIcon, CheckCircleIcon } from '../common/SvgIcons';

interface TelegramAlertCardProps {
  lat: number;
  lon: number;
  defaultLabel?: string;
}

const RADIUS_OPTIONS = [25, 50, 100, 150];

export const TelegramAlertCard: React.FC<TelegramAlertCardProps> = ({
  lat,
  lon,
  defaultLabel = 'Lokasi saya',
}) => {
  const [radius, setRadius] = useState<number>(50);
  const [label, setLabel] = useState<string>(defaultLabel);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [link, setLink] = useState<string | null>(null);
  const [activeBotName, setActiveBotName] = useState<string>('jagaborneo_bot');
  const [error, setError] = useState<string | null>(null);

  const envBotUsername = import.meta.env.VITE_TELEGRAM_BOT_USERNAME as string | undefined;

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setLink(null);
    try {
      const res = await createTelegramSubscription(lat, lon, radius, label.trim() || defaultLabel);
      const username = envBotUsername || res.bot_username || 'jagaborneo_bot';
      setActiveBotName(username.replace(/^@/, ''));
      setLink(res.deep_link || `https://t.me/${username.replace(/^@/, '')}?start=${res.token}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Gagal membuat tautan alert Telegram.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className="risk-modal__telegram" aria-label="Langganan Peringatan Telegram">
      <div className="risk-modal__telegram-header">
        <span className="risk-modal__telegram-title">
          <SendIcon size={14} color="var(--mp-orange)" />
          Peringatan Dini Telegram
        </span>
        <span className="risk-modal__telegram-badge">
          <ClockIcon size={12} color="var(--mp-orange)" />
          Pantau Otomatis
        </span>
      </div>

      <p className="risk-modal__telegram-desc">
        Terima notifikasi otomatis dari bot jika terdeteksi hotspot prediktif tingkat Siaga atau Waspada dalam radius lokasi ini.
      </p>

      <form onSubmit={handleCreate} className="risk-modal__telegram-form">
        <input
          type="text"
          className="risk-modal__telegram-input"
          aria-label="Nama label lokasi"
          placeholder="Nama lokasi (mis. Pos Pantau, Rumah)"
          value={label}
          maxLength={60}
          onChange={(e) => setLabel(e.target.value)}
        />

        <div className="risk-modal__telegram-select-wrap">
          <select
            aria-label="Radius jangkauan pemantauan"
            className="risk-modal__telegram-select"
            value={radius}
            onChange={(e) => setRadius(Number(e.target.value))}
          >
            {RADIUS_OPTIONS.map((r) => (
              <option key={r} value={r}>
                Radius {r} km
              </option>
            ))}
          </select>
          <span className="risk-modal__telegram-arrow" aria-hidden="true">▾</span>
        </div>

        <button
          type="submit"
          className="mp-btn mp-btn--solid risk-modal__button risk-modal__telegram-submit"
          disabled={isLoading}
        >
          <SendIcon size={13} />
          {isLoading ? 'Membuat tautan…' : 'Aktifkan Alert'}
        </button>
      </form>

      {error && (
        <div className="risk-modal__telegram-error" role="alert">
          {error}
        </div>
      )}

      {link && (
        <div className="risk-modal__telegram-ready" role="status">
          <div className="risk-modal__telegram-ready-head">
            <CheckCircleIcon size={14} color="#059669" />
            <span>Tautan aktivasi bot siap</span>
          </div>
          <p className="risk-modal__telegram-ready-text">
            Buka percakapan bot di Telegram lalu tekan tombol <strong>Start</strong> untuk mengonfirmasi lokasi ini.
          </p>
          <a
            href={link}
            target="_blank"
            rel="noreferrer"
            className="mp-btn mp-btn--solid risk-modal__button risk-modal__telegram-link-btn"
          >
            <SendIcon size={12} />
            Buka Telegram (@{activeBotName})
          </a>
          <span className="risk-modal__telegram-hint">
            Kelola langganan langsung di bot melalui perintah /lokasi atau /stop.
          </span>
        </div>
      )}

      <div className="risk-modal__telegram-footer">
        Pemeriksaan hotspot prediktif berjalan otomatis setiap 15 menit. Peringatan hanya dikirim saat ada titik rawan baru di dalam radius.
      </div>
    </section>
  );
};
