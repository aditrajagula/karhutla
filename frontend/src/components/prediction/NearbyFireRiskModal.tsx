import React from 'react';
import type { FireRiskPrediction } from '../../types/prediction';
import type { Hotspot } from '../../types/hotspot';
import type { CitizenReport } from '../../types/report';
import {
  TargetIcon,
  PinIcon,
  RefreshIcon,
  AlertTriangleIcon,
  RadarIcon,
  WeatherSunCloudIcon,
  ThermometerIcon,
  DropletIcon,
  RainIcon,
  WindIcon,
  TreeIcon,
  MountainIcon,
  ActivityIcon,
  FlameIcon,
  MegaphoneIcon,
  SparklesIcon,
  LightbulbIcon,
  MapPinIcon,
  TrendUpIcon,
  TrendDownIcon,
  StatusPillDot,
  CloseIcon,
  InfoCircleIcon,
} from '../common/SvgIcons';
import { TelegramAlertCard } from './TelegramAlertCard';


interface NearbyFireRiskModalProps {
  isOpen: boolean;
  onClose: () => void;
  isLoading: boolean;
  error: string | null;
  prediction: FireRiskPrediction | null;
  userCoords: { lat: number; lon: number; accuracy?: number } | null;
  hotspots?: Hotspot[];
  reports?: CitizenReport[];
  onRefreshGps: () => void;
  onSelectSampleLocation?: (lat: number, lon: number, name: string) => void;
  onFocusMap?: () => void;
  isDark?: boolean;
}

// Formula Haversine untuk menghitung jarak geospasial dalam kilometer
function calculateDistanceKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371; // Radius bumi dalam km
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

const SAMPLE_LOCATIONS = [
  { name: 'Pontianak (Kalbar)', lat: -0.0263, lon: 109.3425 },
  { name: 'Palangka Raya (Kalteng)', lat: -2.2161, lon: 113.914 },
  { name: 'Banjarmasin (Kalsel)', lat: -3.3167, lon: 114.5901 },
  { name: 'Samarinda (Kaltim)', lat: -0.5016, lon: 117.1537 },
  { name: 'Tanjung Selor (Kaltara)', lat: 2.8375, lon: 117.3653 },
];

export const NearbyFireRiskModal: React.FC<NearbyFireRiskModalProps> = ({
  isOpen,
  onClose,
  isLoading,
  error,
  prediction,
  userCoords,
  hotspots = [],
  reports = [],
  onRefreshGps,
  onSelectSampleLocation,
  onFocusMap,
  isDark = false,
}) => {
  if (!isOpen) return null;

  // Analisis titik di sekitar (radius 50 km)
  let nearbyHotspotsCount = 0;
  let closestHotspotDist: number | null = null;
  let nearbyReportsCount = 0;

  if (userCoords) {
    for (const h of hotspots) {
      const dist = calculateDistanceKm(userCoords.lat, userCoords.lon, h.latitude, h.longitude);
      if (dist <= 50) nearbyHotspotsCount++;
      if (closestHotspotDist === null || dist < closestHotspotDist) {
        closestHotspotDist = dist;
      }
    }

    for (const r of reports) {
      if (r.status === 'REJECTED') continue;
      const dist = calculateDistanceKm(userCoords.lat, userCoords.lon, r.latitude, r.longitude);
      if (dist <= 50) nearbyReportsCount++;
    }
  }

  // Pengaturan tingkat risiko
  const riskLevel = prediction?.risk_level || 'BELUM_DAPAT_DINILAI';
  const riskPercent = prediction?.risk_percentage ?? 0;

  let riskDesc =
    prediction?.data_quality?.status === 'PARTIAL'
      ? 'Indikasi risiko rendah terdeteksi dari parameter cuaca dan kanopi, namun estimasi ini memiliki keterbatasan karena data kedalaman gambut dan riwayat perambahan belum terintegrasi. Bukan jaminan mutlak aman di lapangan.'
      : 'Kondisi cuaca dan tutupan kanopi mengindikasikan potensi risiko rendah terhadap penjalaran api.';
  if (riskLevel === 'SEDANG') {
    riskDesc = 'Waspada: Suhu udara hangat dan kelembaban berkurang, potensi penyalaan api sedang.';
  } else if (riskLevel === 'TINGGI') {
    riskDesc = 'Bahaya tinggi: Kondisi kering, panas, atau berangin tinggi memicu percepatan kebakaran lahan.';
  } else if (
    riskLevel === 'TIDAK_DAPAT_DINILAI' ||
    prediction?.status === 'OUT_OF_SCOPE' ||
    prediction?.status === 'INSUFFICIENT_DATA'
  ) {
    riskDesc =
      prediction?.message ||
      'Tingkat risiko karhutla tidak dapat dinilai karena keterbatasan cakupan spasial atau ketiadaan data wajib.';
  }

  const features = prediction?.input_features;

  // Palet tema JagaBorneo
  const theme = {
    modalBg: isDark ? '#11100D' : '#FFFDFA',
    modalBorder: isDark ? 'rgba(204, 111, 0, 0.45)' : 'rgba(204, 111, 0, 0.3)',
    cardBg: isDark ? '#1A1916' : '#F9F7F4',
    cardBorder: isDark ? 'rgba(204, 111, 0, 0.25)' : 'rgba(204, 111, 0, 0.18)',
    textMain: isDark ? '#FFFDFA' : '#11100D',
    textMuted: isDark ? '#CC6F00' : '#B45309',
    textSubtle: isDark ? 'rgba(255, 253, 250, 0.65)' : '#6B6862',
    accentOrange: '#CC6F00',
    accentOrangeHover: '#E07B00',
  };

  const statusColor =
    riskLevel === 'TINGGI'
      ? '#EF4444'
      : riskLevel === 'SEDANG'
      ? '#F59E0B'
      : riskLevel === 'RENDAH'
      ? '#10B981'
      : '#9CA3AF';

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="nearby-risk-title"
      className="modal-backdrop"
      style={{
        backgroundColor: 'rgba(0, 0, 0, 0.72)',
        backdropFilter: 'blur(4px)',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="modal-card"
        style={{
          maxWidth: '680px',
          maxHeight: '92vh',
          overflowY: 'auto',
          backgroundColor: theme.modalBg,
          border: `1.5px solid ${theme.modalBorder}`,
          borderRadius: '14px',
          boxShadow: isDark
            ? '0 20px 48px rgba(0, 0, 0, 0.8), 0 0 1px rgba(204, 111, 0, 0.5)'
            : '0 20px 48px rgba(204, 111, 0, 0.12)',
          color: theme.textMain,
          padding: 0,
        }}
      >
        {/* Header Modal */}
        <div
          className="modal-header"
          style={{
            padding: '16px 22px',
            borderBottom: `1px solid ${theme.modalBorder}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '38px',
                height: '38px',
                borderRadius: '10px',
                background: 'rgba(204, 111, 0, 0.15)',
                color: theme.accentOrange,
              }}
            >
              <TargetIcon size={20} color={theme.accentOrange} />
            </span>
            <div>
              <h3
                id="nearby-risk-title"
                style={{
                  margin: 0,
                  fontSize: '17px',
                  fontWeight: 600,
                  color: theme.textMain,
                  letterSpacing: '-0.02em',
                }}
              >
                Indeks Kerentanan Cuaca & Kanopi (Eksperimental)
              </h3>
              <div style={{ fontSize: '12px', color: theme.textMuted, marginTop: '2px' }}>
                Berdasarkan Mikroklimat Satelit & Tutupan Hutan (Model Prototipe)
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Tutup jendela prediksi"
            style={{
              background: isDark ? 'rgba(204, 111, 0, 0.12)' : 'rgba(0, 0, 0, 0.05)',
              border: `1px solid ${theme.cardBorder}`,
              color: theme.textMain,
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              transition: 'opacity 0.15s ease',
            }}
          >
            <CloseIcon size={16} />
          </button>
        </div>

        <div style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Header Info Lokasi GPS Pengguna */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '10px',
              padding: '12px 16px',
              borderRadius: '10px',
              backgroundColor: theme.cardBg,
              border: `1px solid ${theme.cardBorder}`,
            }}
          >
            <div>
              <div style={{ fontSize: '11px', color: theme.textMuted, fontWeight: 600, display: 'flex', alignItems: 'center', gap: '5px' }}>
                <PinIcon size={13} color={theme.accentOrange} />
                <span>Lokasi Pemantauan:</span>
              </div>
              <div
                style={{
                  fontSize: '14px',
                  fontWeight: 700,
                  fontFamily: 'monospace',
                  color: theme.textMain,
                  marginTop: '3px',
                }}
              >
                {userCoords
                  ? `${userCoords.lat.toFixed(4)}°, ${userCoords.lon.toFixed(4)}°`
                  : 'Mencari sinyal GPS...'}
                {userCoords?.accuracy ? (
                  <span style={{ fontSize: '11px', fontWeight: 400, color: theme.textSubtle, marginLeft: '6px' }}>
                    (Akurasi ±{Math.round(userCoords.accuracy)} m)
                  </span>
                ) : null}
              </div>
              <div style={{ fontSize: '11px', color: theme.textSubtle, marginTop: '2px' }}>
                Wilayah: <b style={{ color: theme.textMain }}>{prediction?.province || 'Kalimantan dan Sekitarnya'}</b>
              </div>
            </div>

            <button
              type="button"
              onClick={onRefreshGps}
              disabled={isLoading}
              style={{
                fontSize: '13px',
                padding: '8px 16px',
                borderRadius: '8px',
                backgroundColor: 'transparent',
                border: `1px solid ${theme.accentOrange}`,
                color: theme.accentOrange,
                cursor: isLoading ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontWeight: 600,
                transition: 'all 0.15s ease',
              }}
              title="Perbarui koordinat GPS dari perangkat"
            >
              <RefreshIcon size={14} color={theme.accentOrange} />
              <span>{isLoading ? 'Memproses...' : 'Segarkan GPS'}</span>
            </button>
          </div>

          {/* Kondisi Error / GPS Gagal */}
          {error && (
            <div
              style={{
                padding: '14px 16px',
                borderRadius: '10px',
                backgroundColor: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.35)',
                color: isDark ? '#FCA5A5' : '#DC2626',
                fontSize: '12px',
              }}
            >
              <div style={{ fontWeight: 700, marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <AlertTriangleIcon size={16} color={isDark ? '#FCA5A5' : '#DC2626'} />
                <span>Kendala Deteksi Lokasi:</span>
              </div>
              <p style={{ margin: 0, lineHeight: 1.5 }}>{error}</p>

              {onSelectSampleLocation && (
                <div style={{ marginTop: '12px' }}>
                  <div style={{ fontSize: '11px', fontWeight: 600, color: theme.textMain, marginBottom: '6px' }}>
                    Atau pilih salah satu titik lokasi simulasi di Kalimantan:
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {SAMPLE_LOCATIONS.map((loc) => (
                      <button
                        key={loc.name}
                        type="button"
                        onClick={() => onSelectSampleLocation(loc.lat, loc.lon, loc.name)}
                        style={{
                          fontSize: '11px',
                          padding: '6px 10px',
                          borderRadius: '6px',
                          border: `1px solid ${theme.cardBorder}`,
                          backgroundColor: theme.cardBg,
                          color: theme.textMain,
                          cursor: 'pointer',
                          fontWeight: 500,
                          display: 'flex',
                          alignItems: 'center',
                          gap: '5px',
                        }}
                      >
                        <PinIcon size={12} color={theme.accentOrange} />
                        <span>{loc.name}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Animasi Loading */}
          {isLoading && (
            <div
              style={{
                padding: '36px 20px',
                textAlign: 'center',
                backgroundColor: theme.cardBg,
                borderRadius: '10px',
                border: `1px dashed ${theme.accentOrange}`,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '10px' }}>
                <RadarIcon size={34} color={theme.accentOrange} />
              </div>
              <div style={{ fontSize: '14px', fontWeight: 600, color: theme.textMain }}>
                Memeriksa Kondisi Cuaca & Lingkungan...
              </div>
              <div style={{ fontSize: '12px', color: theme.textMuted, marginTop: '4px' }}>
                Mengambil data cuaca terkini dan informasi tutupan pepohonan di sekitar Anda.
              </div>
            </div>
          )}

          {/* Status Penolakan / Di Luar Cakupan / Data Tidak Memadai */}
          {!isLoading && prediction && (prediction.status === 'OUT_OF_SCOPE' || prediction.status === 'INSUFFICIENT_DATA' || prediction.status === 'UNAVAILABLE') && (
            <div
              style={{
                padding: '20px 22px',
                borderRadius: '12px',
                background: isDark
                  ? 'linear-gradient(135deg, #24221F 0%, #1A1916 100%)'
                  : 'linear-gradient(135deg, #F3F4F6 0%, #E5E7EB 100%)',
                border: isDark
                  ? '1.5px solid rgba(156, 163, 175, 0.3)'
                  : '1.5px solid rgba(107, 114, 128, 0.3)',
                boxShadow: '0 6px 20px rgba(0, 0, 0, 0.12)',
                display: 'flex',
                flexDirection: 'column',
                gap: '14px',
                color: isDark ? '#FFFDFA' : '#11100D',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
                <div>
                  <div
                    style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      textTransform: 'uppercase',
                      letterSpacing: '0.08em',
                      color: isDark ? '#9CA3AF' : '#6B7280',
                    }}
                  >
                    Status Penilaian Risiko Prediktif
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
                    <h2
                      style={{
                        margin: 0,
                        fontSize: '20px',
                        fontWeight: 800,
                        color: isDark ? '#FFFDFA' : '#11100D',
                        letterSpacing: '-0.02em',
                      }}
                    >
                      {prediction.status === 'OUT_OF_SCOPE'
                        ? 'DI LUAR CAKUPAN'
                        : prediction.status === 'INSUFFICIENT_DATA'
                        ? 'DATA TIDAK MEMADAI'
                        : 'MODEL TIDAK TERSEDIA'}
                    </h2>
                    <span
                      style={{
                        padding: '3px 10px',
                        borderRadius: '999px',
                        background: isDark ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.08)',
                        border: '1px solid rgba(156, 163, 175, 0.3)',
                        fontSize: '11px',
                        fontWeight: 700,
                        color: isDark ? '#D1D5DB' : '#4B5563',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                      }}
                    >
                      <StatusPillDot color="#9CA3AF" size={8} />
                      <span>{prediction.risk_label || 'Tidak Dapat Dinilai'}</span>
                    </span>
                  </div>
                </div>

                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '28px', fontWeight: 800, color: isDark ? '#9CA3AF' : '#6B7280', lineHeight: 1 }}>
                    N/A
                  </div>
                  <div style={{ fontSize: '11px', color: isDark ? 'rgba(255, 253, 250, 0.65)' : '#6B7280', marginTop: '4px' }}>
                    Indeks: <b>Tidak Tersedia</b>
                  </div>
                </div>
              </div>

              <div
                style={{
                  fontSize: '12px',
                  color: isDark ? '#F3F4F6' : '#1F2937',
                  lineHeight: 1.5,
                  backgroundColor: isDark ? 'rgba(0, 0, 0, 0.3)' : 'rgba(255, 255, 255, 0.7)',
                  borderRadius: '8px',
                  padding: '10px 14px',
                  border: isDark ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.08)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                  <InfoCircleIcon size={16} color={isDark ? '#9CA3AF' : '#6B7280'} style={{ marginTop: '2px', flexShrink: 0 }} />
                  <div>
                    {prediction.message || (
                      prediction.status === 'OUT_OF_SCOPE'
                        ? 'Koordinat ini berada di luar batas wilayah 5 provinsi Kalimantan yang didukung oleh model pembelajaran mesin FireGuard. Risiko kebakaran tidak dapat dinilai. Hal ini BUKAN berarti lokasi bebas dari api.'
                        : 'Data wajib tutupan kanopi tidak memadai untuk mengevaluasi tingkat risiko karhutla secara objektif. Hal ini BUKAN berarti lokasi aman dari risiko kebakaran.'
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Hasil Prediksi Risiko */}
          {!isLoading && prediction && prediction.status === 'SUCCESS' && (
            <>
              {/* BANNER TRANSPARANSI KUALITAS DATA */}
              {prediction.data_quality?.status === 'PARTIAL' && (
                <div
                  style={{
                    padding: '10px 14px',
                    borderRadius: '8px',
                    backgroundColor: isDark ? 'rgba(245, 158, 11, 0.12)' : 'rgba(245, 158, 11, 0.08)',
                    border: '1px solid rgba(245, 158, 11, 0.35)',
                    fontSize: '11px',
                    color: isDark ? '#FDE68A' : '#92400E',
                    lineHeight: 1.5,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                    <AlertTriangleIcon size={14} color="#D97706" style={{ marginTop: '2px', flexShrink: 0 }} />
                    <div>
                      <b>Perhatian (Data Parsial / Prototipe):</b> Indeks ini dihitung tanpa layer kedalaman lahan gambut dan riwayat perambahan hutan (fitur belum terintegrasi). Model memprediksi anomali termal satelit (FRP), <i>bukan konfirmasi kebakaran darat terverifikasi</i>. Jangan dijadikan acuan tunggal keselamatan lapangan.
                    </div>
                  </div>
                </div>
              )}

              {/* HERO CARD: PREDIKSI SKOR KARHUTLA DENGAN BACKGROUND ORANGE */}
              <div
                style={{
                  padding: '20px 22px',
                  borderRadius: '12px',
                  background: 'linear-gradient(135deg, #CC6F00 0%, #D97706 50%, #B45309 100%)',
                  border: '1.5px solid rgba(255, 255, 255, 0.25)',
                  boxShadow: '0 8px 24px rgba(204, 111, 0, 0.35)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '14px',
                  color: '#FFFDFA',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
                  <div>
                    <div
                      style={{
                        fontSize: '11px',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        letterSpacing: '0.08em',
                        color: 'rgba(255, 253, 250, 0.9)',
                      }}
                    >
                      Indeks Kerentanan Cuaca & Kanopi (Eksperimental)
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
                      <h2
                        style={{
                          margin: 0,
                          fontSize: '26px',
                          fontWeight: 800,
                          color: '#FFFDFA',
                          letterSpacing: '-0.02em',
                        }}
                      >
                        RISIKO {riskLevel}
                      </h2>
                      <span
                        style={{
                          padding: '3px 10px',
                          borderRadius: '999px',
                          background: 'rgba(0, 0, 0, 0.22)',
                          border: '1px solid rgba(255, 255, 255, 0.3)',
                          fontSize: '11px',
                          fontWeight: 700,
                          color: '#FFFDFA',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                        }}
                      >
                        <StatusPillDot color={statusColor} size={8} />
                        <span>
                          {prediction.risk_label
                            ? prediction.risk_label
                            : riskLevel === 'TINGGI'
                            ? 'Bahaya'
                            : riskLevel === 'SEDANG'
                            ? 'Waspada'
                            : prediction.data_quality?.status === 'PARTIAL'
                            ? 'Rendah (Data Terbatas)'
                            : 'Rendah'}
                        </span>
                      </span>
                    </div>
                  </div>

                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '36px', fontWeight: 800, color: '#FFFDFA', lineHeight: 1 }}>
                      {riskPercent.toFixed(1)}%
                    </div>
                    <div style={{ fontSize: '11px', color: 'rgba(255, 253, 250, 0.85)', marginTop: '4px' }}>
                      Potensi Risiko: <b>{riskPercent.toFixed(1)}%</b>
                    </div>
                  </div>
                </div>

                {/* Progress / Meter Bar */}
                <div>
                  <div
                    style={{
                      height: '10px',
                      borderRadius: '999px',
                      backgroundColor: 'rgba(0, 0, 0, 0.28)',
                      border: '1px solid rgba(255, 255, 255, 0.2)',
                      overflow: 'hidden',
                      position: 'relative',
                    }}
                  >
                    <div
                      style={{
                        height: '100%',
                        width: `${Math.min(Math.max(riskPercent, 2), 100)}%`,
                        backgroundColor: '#FFFDFA',
                        borderRadius: '999px',
                        boxShadow: '0 0 10px rgba(255, 255, 255, 0.8)',
                        transition: 'width 0.4s ease-in-out',
                      }}
                    />
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: '10px',
                      fontWeight: 600,
                      color: 'rgba(255, 253, 250, 0.9)',
                      marginTop: '5px',
                    }}
                  >
                    <span>0% (Indikasi Rendah)</span>
                    <span>35% (Waspada)</span>
                    <span>70% (Bahaya)</span>
                    <span>100%</span>
                  </div>
                </div>

                <div
                  style={{
                    fontSize: '12px',
                    color: '#FFFDFA',
                    lineHeight: 1.5,
                    backgroundColor: 'rgba(0, 0, 0, 0.18)',
                    borderRadius: '8px',
                    padding: '8px 12px',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                  }}
                >
                  {riskDesc}
                </div>
              </div>

              {/* Grid Cuaca & Kondisi Lingkungan */}
              <div>
                <div
                  style={{
                    fontSize: '13px',
                    fontWeight: 700,
                    marginBottom: '10px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    color: theme.textMain,
                  }}
                >
                  <WeatherSunCloudIcon size={17} color={theme.accentOrange} />
                  <span>Kondisi Cuaca & Lingkungan Terkini</span>
                </div>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                    gap: '10px',
                  }}
                >
                  <div
                    style={{
                      padding: '12px 14px',
                      borderRadius: '8px',
                      border: `1px solid ${theme.cardBorder}`,
                      backgroundColor: theme.cardBg,
                    }}
                  >
                    <div style={{ fontSize: '11px', color: theme.textMuted, fontWeight: 500, display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <ThermometerIcon size={13} color={theme.accentOrange} />
                      <span>Suhu Udara</span>
                    </div>
                    <div style={{ fontSize: '17px', fontWeight: 700, color: theme.textMain, marginTop: '3px' }}>
                      {features?.t2m !== undefined ? `${features.t2m} °C` : '-'}
                    </div>
                  </div>

                  <div
                    style={{
                      padding: '12px 14px',
                      borderRadius: '8px',
                      border: `1px solid ${theme.cardBorder}`,
                      backgroundColor: theme.cardBg,
                    }}
                  >
                    <div style={{ fontSize: '11px', color: theme.textMuted, fontWeight: 500, display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <DropletIcon size={13} color={theme.accentOrange} />
                      <span>Kelembapan Udara</span>
                    </div>
                    <div style={{ fontSize: '17px', fontWeight: 700, color: theme.textMain, marginTop: '3px' }}>
                      {features?.h2m !== undefined ? `${features.h2m} %` : '-'}
                    </div>
                  </div>

                  <div
                    style={{
                      padding: '12px 14px',
                      borderRadius: '8px',
                      border: `1px solid ${theme.cardBorder}`,
                      backgroundColor: theme.cardBg,
                    }}
                  >
                    <div style={{ fontSize: '11px', color: theme.textMuted, fontWeight: 500, display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <RainIcon size={13} color={theme.accentOrange} />
                      <span>Curah Hujan Hari Ini</span>
                    </div>
                    <div style={{ fontSize: '17px', fontWeight: 700, color: theme.textMain, marginTop: '3px' }}>
                      {features?.tp !== undefined ? `${features.tp} mm` : '-'}
                    </div>
                  </div>

                  <div
                    style={{
                      padding: '12px 14px',
                      borderRadius: '8px',
                      border: `1px solid ${theme.cardBorder}`,
                      backgroundColor: theme.cardBg,
                    }}
                  >
                    <div style={{ fontSize: '11px', color: theme.textMuted, fontWeight: 500, display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <WindIcon size={13} color={theme.accentOrange} />
                      <span>Kecepatan Angin</span>
                    </div>
                    <div style={{ fontSize: '17px', fontWeight: 700, color: theme.textMain, marginTop: '3px' }}>
                      {features?.w10 !== undefined ? `${features.w10} m/s` : '-'}
                    </div>
                  </div>

                  <div
                    style={{
                      padding: '12px 14px',
                      borderRadius: '8px',
                      border: `1px solid ${theme.cardBorder}`,
                      backgroundColor: theme.cardBg,
                    }}
                  >
                    <div style={{ fontSize: '11px', color: theme.textMuted, fontWeight: 500, display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <TreeIcon size={13} color={theme.accentOrange} />
                      <span>Kerapatan Tutupan Pohon</span>
                    </div>
                    <div style={{ fontSize: '17px', fontWeight: 700, color: theme.textMain, marginTop: '3px' }}>
                      {features?.f_prim !== undefined ? `${Math.round(features.f_prim * 100)} %` : '-'}
                    </div>
                  </div>

                  <div
                    style={{
                      padding: '12px 14px',
                      borderRadius: '8px',
                      border: `1px solid ${theme.cardBorder}`,
                      backgroundColor: theme.cardBg,
                    }}
                  >
                    <div style={{ fontSize: '11px', color: theme.textMuted, fontWeight: 500, display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <MountainIcon size={13} color={theme.accentOrange} />
                      <span>Ketinggian Wilayah</span>
                    </div>
                    <div style={{ fontSize: '17px', fontWeight: 700, color: theme.textMain, marginTop: '3px' }}>
                      {features?.dem !== undefined ? `${Math.round(features.dem)} mdpl` : '-'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Pemantauan Lingkungan Sekitar (Radius 50 km) */}
              <div
                style={{
                  padding: '14px 16px',
                  borderRadius: '10px',
                  border: `1px solid ${theme.cardBorder}`,
                  backgroundColor: theme.cardBg,
                }}
              >
                <div
                  style={{
                    fontSize: '13px',
                    fontWeight: 700,
                    marginBottom: '8px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    color: theme.textMain,
                  }}
                >
                  <ActivityIcon size={16} color={theme.accentOrange} />
                  <span>Pantauan Aktivitas di Sekitar Anda (Radius 50 km)</span>
                </div>
                <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap', fontSize: '13px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <FlameIcon size={15} color={theme.accentOrange} />
                    <span>
                      <b style={{ color: theme.accentOrange }}>{nearbyHotspotsCount}</b> Titik Panas Terdeteksi
                      {closestHotspotDist !== null && (
                        <span style={{ color: theme.textSubtle, marginLeft: '4px' }}>
                          (terdekat ~{closestHotspotDist.toFixed(1)} km)
                        </span>
                      )}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <MegaphoneIcon size={15} color="#30AFFF" />
                    <span>
                      <b style={{ color: '#30AFFF' }}>{nearbyReportsCount}</b> Laporan Warga Masuk
                    </span>
                  </div>
                </div>
              </div>

              {/* Driver Faktor Penentu Risiko */}
              {prediction.primary_drivers && prediction.primary_drivers.length > 0 && (
                <div>
                  <div
                    style={{
                      fontSize: '13px',
                      fontWeight: 700,
                      marginBottom: '4px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      color: theme.textMain,
                    }}
                  >
                    <SparklesIcon size={16} color={theme.accentOrange} />
                    <span>Variabel dengan Deviasi Terbesar terhadap Baseline Model</span>
                  </div>
                  <div style={{ fontSize: '11px', color: theme.textSubtle, marginBottom: '8px' }}>
                    Kontribusi linier terhadap logit model statistik (bukan bukti kausalitas langsung)
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {prediction.primary_drivers.map((drv, idx) => {
                      const isIncreasing = drv.impact.includes('Tinggi') || drv.impact.includes('Meningkatkan');
                      const isNeutral = drv.impact.includes('Netral');
                      const friendlyLabel = drv.label
                        .replace(/Suhu Udara Permukaan \(2m\)/i, 'Suhu Udara Permukaan')
                        .replace(/Elevasi Topografi \(Ketinggian\)/i, 'Ketinggian Lokasi')
                        .replace(/Curah Hujan Bulan Ini/i, 'Curah Hujan 30 Hari')
                        .replace(/Defisit Curah Hujan 1 Bulan Lalu/i, 'Kekurangan Hujan 1 Bln Lalu')
                        .replace(/Kehilangan Hutan Primer Tahun Lalu/i, 'Pengurangan Area Hutan Primer')
                        .replace(/Kerapatan Kanopi/i, 'Kerapatan Tutupan Pohon');

                      return (
                        <div
                          key={idx}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '8px 12px',
                            borderRadius: '8px',
                            backgroundColor: theme.cardBg,
                            border: `1px solid ${theme.cardBorder}`,
                            fontSize: '12px',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            {isNeutral ? (
                              <InfoCircleIcon size={14} color="#94A3B8" />
                            ) : isIncreasing ? (
                              <TrendUpIcon size={14} color="#EF4444" />
                            ) : (
                              <TrendDownIcon size={14} color="#10B981" />
                            )}
                            <span style={{ color: theme.textMain }}>
                              {friendlyLabel}
                              {drv.is_imputed ? (
                                <span style={{ fontSize: '10px', color: theme.textSubtle, marginLeft: '5px' }}>(Imputasi Netral)</span>
                              ) : null}
                            </span>
                          </div>
                          <span
                            style={{
                              padding: '2px 8px',
                              borderRadius: '4px',
                              fontSize: '11px',
                              fontWeight: 600,
                              backgroundColor: isNeutral
                                ? 'rgba(148, 163, 184, 0.15)'
                                : isIncreasing
                                ? 'rgba(239, 68, 68, 0.15)'
                                : 'rgba(16, 185, 129, 0.15)',
                              border: `1px solid ${
                                isNeutral
                                  ? 'rgba(148, 163, 184, 0.35)'
                                  : isIncreasing
                                  ? 'rgba(239, 68, 68, 0.35)'
                                  : 'rgba(16, 185, 129, 0.35)'
                              }`,
                              color: isNeutral
                                ? (isDark ? '#94A3B8' : '#64748B')
                                : isIncreasing
                                ? (isDark ? '#FCA5A5' : '#DC2626')
                                : (isDark ? '#6EE7B7' : '#059669'),
                            }}
                          >
                            {drv.impact}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Rekomendasi Tindakan Warga */}
              <div
                style={{
                  padding: '14px 16px',
                  borderRadius: '10px',
                  backgroundColor: isDark ? 'rgba(204, 111, 0, 0.1)' : 'rgba(204, 111, 0, 0.06)',
                  border: `1px solid ${theme.modalBorder}`,
                  fontSize: '12px',
                  lineHeight: 1.6,
                }}
              >
                <div style={{ fontWeight: 700, color: theme.accentOrange, marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <LightbulbIcon size={16} color={theme.accentOrange} />
                  <span>Rekomendasi Mitigasi Setempat:</span>
                </div>
                <ul style={{ margin: 0, paddingLeft: '18px', color: theme.textMain }}>
                  {riskLevel === 'TINGGI' ? (
                    <>
                      <li>Dilarang keras melakukan pembakaran sisa ladang atau sampah di area terbuka.</li>
                      <li>Siapkan cadangan sumber air dan laporkan segera jika menjumpai titik api di sekitar Anda.</li>
                    </>
                  ) : riskLevel === 'SEDANG' ? (
                    <>
                      <li>Waspadai aktivitas membakar di lahan gambut atau semak belukar yang mulai mengering.</li>
                      <li>Pantau pembaruan peta anomali termal dan laporkan perubahan vegetasi mencurigakan.</li>
                    </>
                  ) : (
                    <>
                      <li>Parameter cuaca mikro saat ini menunjukkan potensi penjalaran rendah, namun tetap pantau informasi kondisi gambut dan lingkungan setempat.</li>
                      <li>Gunakan fitur "Lapor Kejadian" jika menemukan indikasi pembukaan lahan liar.</li>
                    </>
                  )}
                </ul>
              </div>
            </>
          )}

          {userCoords && (
            <TelegramAlertCard lat={userCoords.lat} lon={userCoords.lon} theme={theme} />
          )}
        </div>

        {/* Modal Footer */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 22px',
            borderTop: `1px solid ${theme.modalBorder}`,
            backgroundColor: theme.cardBg,
            borderBottomLeftRadius: '14px',
            borderBottomRightRadius: '14px',
          }}
        >
          {onFocusMap && userCoords ? (
            <button
              type="button"
              onClick={() => {
                onFocusMap();
                onClose();
              }}
              style={{
                height: '42px',
                padding: '0 20px',
                borderRadius: '8px',
                backgroundColor: 'transparent',
                color: theme.accentOrange,
                border: `1.5px solid ${theme.accentOrange}`,
                fontSize: '14px',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                cursor: 'pointer',
                transition: 'opacity 0.15s ease',
              }}
            >
              <MapPinIcon size={16} color={theme.accentOrange} />
              <span>Pusatkan di Peta</span>
            </button>
          ) : <div />}

          <button
            type="button"
            onClick={onClose}
            style={{
              height: '42px',
              padding: '0 24px',
              borderRadius: '8px',
              backgroundColor: theme.accentOrange,
              color: '#FFFDFA',
              border: 'none',
              fontSize: '14px',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'opacity 0.15s ease',
            }}
          >
            Tutup
          </button>
        </div>
      </div>
    </div>
  );
};
export default NearbyFireRiskModal;
