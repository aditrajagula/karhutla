import React from 'react';
import type { FireRiskPrediction } from '../../types/prediction';
import type { Hotspot } from '../../types/hotspot';
import type { CitizenReport } from '../../types/report';

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
      const dist = calculateDistanceKm(userCoords.lat, userCoords.lon, r.latitude, r.longitude);
      if (dist <= 50) nearbyReportsCount++;
    }
  }

  // Pengaturan warna level risiko
  const riskLevel = prediction?.risk_level || 'BELUM_DAPAT_DINILAI';
  const riskPercent = prediction?.risk_percentage ?? 0;

  let riskColor = '#10B981'; // Hijau
  let riskBg = 'rgba(16, 185, 129, 0.12)';
  let riskBorder = '#10B981';
  let riskDesc = 'Kondisi cuaca dan tutupan kanopi relatif aman dari potensi penyebaran kebakaran.';

  if (riskLevel === 'SEDANG') {
    riskColor = '#F59E0B';
    riskBg = 'rgba(245, 158, 11, 0.12)';
    riskBorder = '#F59E0B';
    riskDesc = 'Waspada: Suhu udara hangat dan kelembaban berkurang, potensi penyalaan api sedang.';
  } else if (riskLevel === 'TINGGI') {
    riskColor = '#EF4444';
    riskBg = 'rgba(239, 68, 68, 0.15)';
    riskBorder = '#EF4444';
    riskDesc = 'Bahaya tinggi: Kondisi kering, panas, atau berangin tinggi memicu percepatan kebakaran lahan.';
  }

  const features = prediction?.input_features;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="nearby-risk-title"
      className="modal-backdrop"
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
          backgroundColor: isDark ? 'var(--color-bg-card, #1E293B)' : '#FFFFFF',
        }}
      >
        {/* Header Modal */}
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '22px' }}>🎯</span>
            <div>
              <h3 id="nearby-risk-title" className="modal-title" style={{ margin: 0, fontSize: '16px' }}>
                Prediksi Risiko Karhutla Sekitar Anda
              </h3>
              <div style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>
                Sensor Cuaca Mikro Open-Meteo & Kanopi Hansen GFC v1.13
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Tutup jendela prediksi"
            className="modal-close-btn"
          >
            ✕
          </button>
        </div>

        <div className="modal-body" style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Header Info Lokasi GPS Pengguna */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '8px',
              padding: '10px 14px',
              borderRadius: '8px',
              backgroundColor: 'var(--color-bg-subtle, #F8FAFC)',
              border: '1px solid var(--color-border, #E2E8F0)',
            }}
          >
            <div>
              <div style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>📍 Posisi Geospasial GPS:</div>
              <div className="font-mono" style={{ fontSize: '13px', fontWeight: 600 }}>
                {userCoords
                  ? `${userCoords.lat.toFixed(4)}°, ${userCoords.lon.toFixed(4)}°`
                  : 'Mencari sinyal GPS...'}
                {userCoords?.accuracy ? (
                  <span style={{ fontSize: '11px', fontWeight: 400, color: 'var(--color-text-muted)', marginLeft: '6px' }}>
                    (Akurasi ±{Math.round(userCoords.accuracy)} m)
                  </span>
                ) : null}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                Wilayah: <b>{prediction?.province || 'Kalimantan / Sekitar Pengguna'}</b>
              </div>
            </div>

            <button
              type="button"
              onClick={onRefreshGps}
              disabled={isLoading}
              style={{
                fontSize: '12px',
                padding: '6px 12px',
                borderRadius: '6px',
                backgroundColor: 'var(--color-bg-card, #FFFFFF)',
                border: '1px solid var(--color-border, #CBD5E1)',
                cursor: isLoading ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontWeight: 500,
              }}
              title="Perbarui koordinat GPS dari perangkat"
            >
              <span>🔄</span>
              <span>{isLoading ? 'Memproses...' : 'Segarkan GPS'}</span>
            </button>
          </div>

          {/* Kondisi Error / GPS Gagal */}
          {error && (
            <div
              style={{
                padding: '12px 14px',
                borderRadius: '8px',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#DC2626',
                fontSize: '12px',
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: '4px' }}>⚠️ Kendala Deteksi Lokasi:</div>
              <p style={{ margin: 0, lineHeight: 1.5 }}>{error}</p>

              {onSelectSampleLocation && (
                <div style={{ marginTop: '10px' }}>
                  <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-text-main)', marginBottom: '6px' }}>
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
                          padding: '4px 8px',
                          borderRadius: '4px',
                          border: '1px solid var(--color-border)',
                          backgroundColor: 'var(--color-bg-card)',
                          cursor: 'pointer',
                        }}
                      >
                        📍 {loc.name}
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
                padding: '30px 20px',
                textAlign: 'center',
                backgroundColor: 'var(--color-bg-subtle)',
                borderRadius: '8px',
                border: '1px dashed var(--color-border)',
              }}
            >
              <div style={{ fontSize: '28px', marginBottom: '8px' }}>📡</div>
              <div style={{ fontSize: '13px', fontWeight: 600 }}>Menghubungkan ke Sensor & Model ML...</div>
              <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                Membaca parameter cuaca mikro Open-Meteo dan tutupan kanopi raster Hansen GFC.
              </div>
            </div>
          )}

          {/* Hasil Prediksi Risiko */}
          {!isLoading && prediction && prediction.status === 'SUCCESS' && (
            <>
              {/* Kartu Tingkat Risiko Utama */}
              <div
                style={{
                  padding: '16px 18px',
                  borderRadius: '10px',
                  backgroundColor: riskBg,
                  border: `1.5px solid ${riskBorder}`,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' }}>
                  <div>
                    <span
                      style={{
                        fontSize: '11px',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                        color: riskColor,
                      }}
                    >
                      Indeks Risiko Karhutla
                    </span>
                    <h2 style={{ margin: '4px 0 0 0', fontSize: '24px', fontWeight: 700, color: riskColor }}>
                      RISIKO {riskLevel}
                    </h2>
                  </div>

                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '28px', fontWeight: 800, color: riskColor }}>
                      {riskPercent.toFixed(1)}%
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>
                      Probabilitas Model: {prediction.risk_probability?.toFixed(4)}
                    </div>
                  </div>
                </div>

                {/* Progress / Meter Bar */}
                <div>
                  <div
                    style={{
                      height: '10px',
                      borderRadius: '5px',
                      backgroundColor: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)',
                      overflow: 'hidden',
                      position: 'relative',
                    }}
                  >
                    <div
                      style={{
                        height: '100%',
                        width: `${Math.min(Math.max(riskPercent, 2), 100)}%`,
                        backgroundColor: riskColor,
                        borderRadius: '5px',
                        transition: 'width 0.4s ease-in-out',
                      }}
                    />
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: '10px',
                      color: 'var(--color-text-muted)',
                      marginTop: '4px',
                    }}
                  >
                    <span>0% (Rendah)</span>
                    <span>35% (Ambang Sedang)</span>
                    <span>70% (Ambang Tinggi)</span>
                    <span>100%</span>
                  </div>
                </div>

                <div style={{ fontSize: '12px', color: 'var(--color-text-main)', lineHeight: 1.5 }}>
                  {riskDesc}
                </div>
              </div>

              {/* Grid Cuaca Mikro Real-Time */}
              <div>
                <div style={{ fontSize: '12px', fontWeight: 700, marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span>🌤️</span>
                  <span>Parameter Cuaca Mikro Terkini ({prediction.weather_source})</span>
                </div>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                    gap: '10px',
                  }}
                >
                  <div style={{ padding: '10px 12px', borderRadius: '6px', border: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg-subtle)' }}>
                    <div style={{ fontSize: '10px', color: 'var(--color-text-muted)' }}>Suhu Udara (2m)</div>
                    <div style={{ fontSize: '16px', fontWeight: 700, marginTop: '2px' }}>
                      {features?.t2m !== undefined ? `${features.t2m} °C` : '-'}
                    </div>
                  </div>

                  <div style={{ padding: '10px 12px', borderRadius: '6px', border: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg-subtle)' }}>
                    <div style={{ fontSize: '10px', color: 'var(--color-text-muted)' }}>Kelembaban Relatif</div>
                    <div style={{ fontSize: '16px', fontWeight: 700, marginTop: '2px' }}>
                      {features?.h2m !== undefined ? `${features.h2m} %` : '-'}
                    </div>
                  </div>

                  <div style={{ padding: '10px 12px', borderRadius: '6px', border: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg-subtle)' }}>
                    <div style={{ fontSize: '10px', color: 'var(--color-text-muted)' }}>Curah Hujan Hari Ini</div>
                    <div style={{ fontSize: '16px', fontWeight: 700, marginTop: '2px' }}>
                      {features?.tp !== undefined ? `${features.tp} mm` : '-'}
                    </div>
                  </div>

                  <div style={{ padding: '10px 12px', borderRadius: '6px', border: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg-subtle)' }}>
                    <div style={{ fontSize: '10px', color: 'var(--color-text-muted)' }}>Kecepatan Angin (10m)</div>
                    <div style={{ fontSize: '16px', fontWeight: 700, marginTop: '2px' }}>
                      {features?.w10 !== undefined ? `${features.w10} m/s` : '-'}
                    </div>
                  </div>

                  <div style={{ padding: '10px 12px', borderRadius: '6px', border: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg-subtle)' }}>
                    <div style={{ fontSize: '10px', color: 'var(--color-text-muted)' }}>Kerapatan Kanopi Pohon</div>
                    <div style={{ fontSize: '16px', fontWeight: 700, marginTop: '2px' }}>
                      {features?.f_prim !== undefined ? `${Math.round(features.f_prim * 100)} %` : '-'}
                    </div>
                  </div>

                  <div style={{ padding: '10px 12px', borderRadius: '6px', border: '1px solid var(--color-border)', backgroundColor: 'var(--color-bg-subtle)' }}>
                    <div style={{ fontSize: '10px', color: 'var(--color-text-muted)' }}>Elevasi Topografi</div>
                    <div style={{ fontSize: '16px', fontWeight: 700, marginTop: '2px' }}>
                      {features?.dem !== undefined ? `${Math.round(features.dem)} mdpl` : '-'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Pemantauan Lingkungan Sekitar (Radius 50 km) */}
              <div
                style={{
                  padding: '12px 14px',
                  borderRadius: '8px',
                  border: '1px solid var(--color-border)',
                  backgroundColor: 'var(--color-bg-subtle)',
                }}
              >
                <div style={{ fontSize: '12px', fontWeight: 700, marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span>🔭</span>
                  <span>Deteksi Lapangan di Sekitar Anda (Radius 50 km)</span>
                </div>
                <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', fontSize: '12px' }}>
                  <div>
                    🔥 <b>{nearbyHotspotsCount}</b> Hotspot Satelit terdeteksi
                    {closestHotspotDist !== null && (
                      <span style={{ color: 'var(--color-text-muted)', marginLeft: '4px' }}>
                        (terdekat ~{closestHotspotDist.toFixed(1)} km)
                      </span>
                    )}
                  </div>
                  <div>
                    📢 <b>{nearbyReportsCount}</b> Laporan Warga terdaftar
                  </div>
                </div>
              </div>

              {/* Driver Faktor Penentu Model ML */}
              {prediction.primary_drivers && prediction.primary_drivers.length > 0 && (
                <div>
                  <div style={{ fontSize: '12px', fontWeight: 700, marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>🧠</span>
                    <span>Faktor Pemicu Terbesar (Explainability Model)</span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {prediction.primary_drivers.map((drv, idx) => {
                      const isIncreasing = drv.impact === 'Meningkatkan Risiko';
                      return (
                        <div
                          key={idx}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '6px 10px',
                            borderRadius: '6px',
                            backgroundColor: 'var(--color-bg-card)',
                            border: '1px solid var(--color-border)',
                            fontSize: '11px',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span style={{ color: isIncreasing ? '#EF4444' : '#10B981' }}>
                              {isIncreasing ? '▲' : '▼'}
                            </span>
                            <span>{drv.label}</span>
                          </div>
                          <span
                            style={{
                              padding: '2px 6px',
                              borderRadius: '4px',
                              fontSize: '10px',
                              fontWeight: 600,
                              backgroundColor: isIncreasing ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)',
                              color: isIncreasing ? '#DC2626' : '#059669',
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
                  padding: '12px 14px',
                  borderRadius: '8px',
                  backgroundColor: 'rgba(59, 130, 246, 0.08)',
                  border: '1px solid rgba(59, 130, 246, 0.25)',
                  fontSize: '11px',
                  lineHeight: 1.5,
                }}
              >
                <b>💡 Rekomendasi Mitigasi Setempat:</b>
                <ul style={{ margin: '4px 0 0 0', paddingLeft: '16px' }}>
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
                      <li>Kondisi vegetasi dan kelembaban relatif aman, pertahankan kewaspadaan cuaca mikro.</li>
                      <li>Gunakan fitur "Lapor Kejadian" jika menemukan indikasi pembukaan lahan liar.</li>
                    </>
                  )}
                </ul>
              </div>
            </>
          )}
        </div>

        {/* Modal Footer */}
        <div className="modal-footer" style={{ display: 'flex', justifyContent: 'space-between', padding: '12px 20px' }}>
          {onFocusMap && userCoords ? (
            <button
              type="button"
              onClick={() => {
                onFocusMap();
                onClose();
              }}
              className="btn-action"
              style={{
                backgroundColor: 'rgba(59, 130, 246, 0.12)',
                color: isDark ? '#93C5FD' : '#2563EB',
                border: '1px solid #3B82F6',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <span>🗺️</span>
              <span>Pusatkan di Peta</span>
            </button>
          ) : <div />}

          <button
            type="button"
            onClick={onClose}
            className="btn-secondary"
            style={{ minWidth: '90px' }}
          >
            Tutup
          </button>
        </div>
      </div>
    </div>
  );
};
