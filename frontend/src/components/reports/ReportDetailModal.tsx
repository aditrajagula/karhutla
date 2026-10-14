import React, { useEffect } from 'react';
import type { CitizenReport } from '../../types/report';
import { CATEGORY_LABELS, STATUS_LABELS, EVIDENCE_BADGE_CONFIG } from '../../types/report';

interface ReportDetailModalProps {
  report: CitizenReport | null;
  onClose: () => void;
}

export const ReportDetailModal: React.FC<ReportDetailModalProps> = ({
  report,
  onClose,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!report) return null;

  // Status badge tema
  const statusColors = {
    PENDING: { bg: 'rgba(245, 158, 11, 0.15)', text: '#D97706', border: '#D97706' },
    IN_REVIEW: { bg: 'rgba(37, 99, 235, 0.15)', text: '#2563EB', border: '#2563EB' },
    VERIFIED: { bg: 'rgba(16, 185, 129, 0.15)', text: '#059669', border: '#059669' },
    REJECTED: { bg: 'rgba(239, 68, 68, 0.15)', text: '#DC2626', border: '#DC2626' },
  };

  const currentTheme = statusColors[report.status] || statusColors.PENDING;

  // Bukti hasil analisis terpisah
  const evidence = report.evidence_assessment;
  const assessmentLabel = evidence?.category_result || 'Belum dapat dinilai';
  const badgeConfig = EVIDENCE_BADGE_CONFIG[assessmentLabel] || EVIDENCE_BADGE_CONFIG['Belum dapat dinilai'];

  // Buat URL absolut untuk foto jika photo_url ada
  const photoFullUrl = report.photo_url
    ? (report.photo_url.startsWith('http') ? report.photo_url : `http://127.0.0.1:8000${report.photo_url}`)
    : null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="report-detail-title"
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-card" style={{ maxWidth: '640px', maxHeight: '90vh', overflowY: 'auto' }}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '18px' }}>📋</span>
            <h3 id="report-detail-title" className="modal-title">
              Detail Laporan Warga & Penilaian Bukti
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Tutup detail modal"
            className="modal-close-btn"
          >
            ✕
          </button>
        </div>

        <div className="modal-body">
          {/* Header Identitas Laporan */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '10px 14px',
              borderRadius: '6px',
              backgroundColor: 'var(--color-bg-subtle)',
              border: '1px solid var(--color-border)',
              marginBottom: '14px',
            }}
          >
            <div>
              <div style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>Nomor Registrasi Laporan:</div>
              <div className="font-mono" style={{ fontSize: '13px', fontWeight: 600 }}>{report.id}</div>
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  padding: '3px 8px',
                  borderRadius: '4px',
                  backgroundColor: currentTheme.bg,
                  color: currentTheme.text,
                  border: `1px solid ${currentTheme.border}`,
                }}
              >
                Status: {STATUS_LABELS[report.status]}
              </span>
            </div>
          </div>

          {/* Indikasi Duplikasi */}
          {report.is_duplicate_suspect && (
            <div
              style={{
                backgroundColor: 'rgba(245, 158, 11, 0.1)',
                border: '1px solid #D97706',
                color: '#B45309',
                padding: '10px 12px',
                borderRadius: '6px',
                fontSize: '12px',
                marginBottom: '14px',
                lineHeight: 1.4,
              }}
            >
              ⚠️ <b>Indikasi Kemungkinan Duplikat:</b> Laporan ini terdeteksi berada dalam radius &lt; 5 km dan waktu berdekatan dengan laporan pendahulu (<b>{report.duplicate_of_id || 'serupa'}</b>). Data tetap disimpan untuk melengkapi informasi.
            </div>
          )}

          {/* PANEL UTAMA: HASIL PENILAIAN BUKTI ILMIAH */}
          <div
            style={{
              backgroundColor: 'var(--color-bg-subtle)',
              border: `1px solid ${badgeConfig.border}`,
              borderRadius: '8px',
              padding: '14px 16px',
              marginBottom: '16px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--color-text-main)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                Hasil Penilaian Bukti Geospasial
              </span>
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '4px 10px',
                  borderRadius: '12px',
                  fontSize: '11px',
                  fontWeight: 700,
                  backgroundColor: badgeConfig.bg,
                  color: badgeConfig.text,
                  border: `1px solid ${badgeConfig.border}`,
                }}
              >
                <span>{badgeConfig.icon}</span> {assessmentLabel}
              </span>
            </div>

            <p style={{ fontSize: '13px', margin: '6px 0', color: 'var(--color-text-main)', lineHeight: 1.5 }}>
              {evidence?.summary || 'Menunggu pemrosesan pencocokan data penginderaan jauh.'}
            </p>

            {evidence?.matching_rule && (
              <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '6px' }}>
                <b>Aturan Pencocokan:</b> {evidence.matching_rule}
              </div>
            )}

            {/* Rincian Tambahan jika Ada */}
            {evidence?.details && (
              <div
                style={{
                  marginTop: '10px',
                  padding: '8px 10px',
                  borderRadius: '4px',
                  backgroundColor: 'var(--color-bg-card)',
                  border: '1px solid var(--color-border)',
                  fontSize: '11px',
                  lineHeight: 1.6,
                }}
              >
                {report.category === 'kebakaran' && Boolean(evidence.details['distance_km'] !== undefined) && (
                  <div>
                    <div>📍 <b>Jarak ke Hotspot Terdekat:</b> {String(evidence.details['distance_km'])} km</div>
                    <div>🛰️ <b>Satelit & Sensor:</b> {String(evidence.details['satellite'] || 'VIIRS')} ({String(evidence.details['instrument'] || 'VIIRS')})</div>
                    <div>🕒 <b>Waktu Akuisisi Satelit:</b> {String(evidence.details['acq_date'])} pk. {String(evidence.details['acq_time'])} UTC</div>
                    <div>🔥 <b>FRP:</b> {String(evidence.details['frp_mw'] ?? '-')} MW | <b>Confidence:</b> {String(evidence.details['confidence'] ?? '-')}</div>
                  </div>
                )}
                {report.category !== 'kebakaran' && Boolean(evidence.details['dataset']) && (
                  <div>
                    <div>📚 <b>Dataset:</b> {String(evidence.details['dataset'])} (UMD/Google/NASA)</div>
                    <div>📐 <b>Resolusi Piksel WGS84:</b> ~{String(evidence.details['pixel_area_ha'] ?? '0.0953')} ha / piksel</div>
                    <div>📅 <b>Periode Analisis:</b> {String(evidence.details['data_period'] ?? '2000–2025')} (Data historis)</div>
                  </div>
                )}
              </div>
            )}


            {/* Catatan Keterbatasan Ilmiah */}
            {evidence?.limitations_caveat && (
              <div
                style={{
                  marginTop: '10px',
                  padding: '8px 10px',
                  borderRadius: '4px',
                  backgroundColor: 'rgba(59, 130, 246, 0.08)',
                  border: '1px solid rgba(59, 130, 246, 0.25)',
                  fontSize: '11px',
                  color: 'var(--color-text-main)',
                  lineHeight: 1.45,
                }}
              >
                ℹ️ <b>Keterbatasan Ilmiah:</b> {evidence.limitations_caveat}
              </div>
            )}
          </div>

          {/* Rincian Laporan Lapangan */}
          <div className="detail-row">
            <span className="detail-label">Kategori Laporan:</span>
            <span className="detail-val" style={{ fontWeight: 600 }}>
              {CATEGORY_LABELS[report.category] || report.category}
            </span>
          </div>

          <div className="detail-row">
            <span className="detail-label">Koordinat Lokasi:</span>
            <span className="detail-val font-mono">
              {report.latitude.toFixed(3)}°, {report.longitude.toFixed(3)}°{' '}
              <span style={{ fontSize: '10px', color: 'var(--color-text-muted)' }}>(Disamarkan ~100m demi privasi)</span>
            </span>
          </div>

          {report.province && (
            <div className="detail-row">
              <span className="detail-label">Provinsi Cakupan:</span>
              <span className="detail-val">
                {report.province}
              </span>
            </div>
          )}

          <div className="detail-row">
            <span className="detail-label">Waktu Pengamatan Warga:</span>
            <span className="detail-val">
              {report.observed_at_utc}
            </span>
          </div>

          <div className="detail-row">
            <span className="detail-label">Pelapor:</span>
            <span className="detail-val">
              {report.reporter_name || 'Warga Masyarakat (Anonim)'}
            </span>
          </div>

          <div className="detail-row" style={{ alignItems: 'flex-start' }}>
            <span className="detail-label">Deskripsi Lapangan:</span>
            <span
              className="detail-val"
              style={{
                background: 'var(--color-bg-subtle)',
                padding: '8px 10px',
                borderRadius: '4px',
                border: '1px solid var(--color-border)',
                whiteSpace: 'pre-wrap',
                flex: 1,
              }}
            >
              {report.description}
            </span>
          </div>

          {/* Foto Bukti */}
          {photoFullUrl && (
            <div className="detail-row" style={{ alignItems: 'flex-start' }}>
              <span className="detail-label">Foto Pendukung:</span>
              <div style={{ flex: 1 }}>
                <a href={photoFullUrl} target="_blank" rel="noopener noreferrer" title="Klik untuk perbesar">
                  <img
                    src={photoFullUrl}
                    alt="Foto pendukung laporan warga"
                    style={{
                      maxWidth: '100%',
                      maxHeight: '220px',
                      borderRadius: '6px',
                      border: '1px solid var(--color-border)',
                      objectFit: 'cover',
                      display: 'block',
                      marginTop: '4px',
                    }}
                  />
                </a>
                <span style={{ fontSize: '11px', color: 'var(--color-text-muted)', display: 'block', marginTop: '3px' }}>
                  Klik gambar untuk melihat resolusi penuh.
                </span>
              </div>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <p className="disclaimer-text">
            Platform FireGuard untuk warga: Informasi warga dipadukan dengan penginderaan jauh satelit untuk transparansi pemantauan hutan Kalimantan tanpa peran petugas tertutup.
          </p>
        </div>
      </div>
    </div>
  );
};
