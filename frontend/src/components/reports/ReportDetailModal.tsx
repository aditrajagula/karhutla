import React, { useEffect, useState } from 'react';
import type { CitizenReport } from '../../types/report';
import { CATEGORY_LABELS, STATUS_LABELS, EVIDENCE_BADGE_CONFIG } from '../../types/report';
import { fetchFireRiskPrediction } from '../../services/api';
import {
  ClipboardIcon,
  CloseIcon,
  AlertTriangleIcon,
  PinIcon,
  SatelliteIcon,
  ClockIcon,
  FlameIcon,
  BookIcon,
  RulerIcon,
  CalendarIcon,
  InfoCircleIcon,
  HourglassIcon,
  ZapIcon,
  SearchIcon,
  StatusPillDot,
} from '../common/SvgIcons';

interface ReportDetailModalProps {
  report: CitizenReport | null;
  onClose: () => void;
}

export const ReportDetailModal: React.FC<ReportDetailModalProps> = ({
  report,
  onClose,
}) => {
  const [riskData, setRiskData] = useState<any>(report?.environmental_risk || null);
  const [loadingRisk, setLoadingRisk] = useState<boolean>(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    if (!report) return;

    if (report.environmental_risk?.risk_level) {
      setRiskData(report.environmental_risk);
      setLoadingRisk(false);
      return;
    }

    let isMounted = true;
    setLoadingRisk(true);
    fetchFireRiskPrediction(report.latitude, report.longitude, report.province || undefined)
      .then((data) => {
        if (isMounted) {
          setRiskData(data);
          setLoadingRisk(false);
        }
      })
      .catch((err) => {
        console.warn('Gagal memuat prediksi risiko cuaca mikro:', err);
        if (isMounted) setLoadingRisk(false);
      });

    return () => {
      isMounted = false;
    };
  }, [report?.id, report?.latitude, report?.longitude, report?.province, report?.environmental_risk]);

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

  const renderBadgeIcon = () => {
    if (assessmentLabel === 'Ada indikasi pendukung') {
      return <ZapIcon size={12} color={badgeConfig.text} />;
    }
    if (assessmentLabel === 'Belum ditemukan kecocokan') {
      return <SearchIcon size={12} color={badgeConfig.text} />;
    }
    return <HourglassIcon size={12} color={badgeConfig.text} />;
  };

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
            <ClipboardIcon size={18} color="#CC6F00" />
            <h3 id="report-detail-title" className="modal-title">
              Detail Laporan Warga & Penilaian Bukti
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Tutup detail modal"
            className="modal-close-btn"
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            <CloseIcon size={16} />
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
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                <AlertTriangleIcon size={16} color="#D97706" style={{ marginTop: '2px', flexShrink: 0 }} />
                <span>
                  <b>Indikasi Kemungkinan Duplikat:</b> Laporan ini terdeteksi berada dalam radius &lt; 5 km dan waktu berdekatan dengan laporan pendahulu (<b>{report.duplicate_of_id || 'serupa'}</b>). Data tetap disimpan untuk melengkapi informasi.
                </span>
              </div>
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
                  gap: '6px',
                  padding: '4px 10px',
                  borderRadius: '12px',
                  fontSize: '11px',
                  fontWeight: 700,
                  backgroundColor: badgeConfig.bg,
                  color: badgeConfig.text,
                  border: `1px solid ${badgeConfig.border}`,
                }}
              >
                {renderBadgeIcon()}
                <span>{assessmentLabel}</span>
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
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <PinIcon size={13} color="var(--color-text-muted)" />
                      <span><b>Jarak ke Titik Panas Terdekat:</b> {String(evidence.details['distance_km'])} km</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <SatelliteIcon size={13} color="var(--color-text-muted)" />
                      <span><b>Sensor Satelit:</b> {String(evidence.details['satellite'] || 'VIIRS')} ({String(evidence.details['instrument'] || 'VIIRS')})</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <ClockIcon size={13} color="var(--color-text-muted)" />
                      <span><b>Waktu Deteksi Satelit:</b> {String(evidence.details['acq_date'])} pk. {String(evidence.details['acq_time'])} UTC</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <FlameIcon size={13} color="#CC6F00" />
                      <span><b>Daya Panas:</b> {String(evidence.details['frp_mw'] ?? '-')} MW | <b>Tingkat Keyakinan:</b> {String(evidence.details['confidence'] ?? '-')}</span>
                    </div>
                  </div>
                )}
                {report.category !== 'kebakaran' && Boolean(evidence.details['dataset']) && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <BookIcon size={13} color="var(--color-text-muted)" />
                      <span><b>Sumber Data:</b> Pemantauan Perubahan Tutupan Pohon</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <RulerIcon size={13} color="var(--color-text-muted)" />
                      <span><b>Cakupan Analisis:</b> Sekitar ~{String(evidence.details['pixel_area_ha'] ?? '0.08')} hektare per titik observasi</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <CalendarIcon size={13} color="var(--color-text-muted)" />
                      <span><b>Periode Analisis:</b> {String(evidence.details['data_period'] ?? '2000–2025')}</span>
                    </div>
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
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                  <InfoCircleIcon size={14} color="#3B82F6" style={{ marginTop: '2px', flexShrink: 0 }} />
                  <span><b>Keterbatasan Ilmiah:</b> {evidence.limitations_caveat}</span>
                </div>
              </div>
            )}
          </div>

          {/* PANEL ESTIMASI RISIKO KEBAKARAN */}
          {loadingRisk && (
            <div
              style={{
                backgroundColor: 'rgba(204, 111, 0, 0.08)',
                border: '1px solid rgba(204, 111, 0, 0.25)',
                borderRadius: '8px',
                padding: '10px 14px',
                marginBottom: '16px',
                fontSize: '12px',
                color: 'var(--color-text-muted)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <HourglassIcon size={14} color="#CC6F00" />
              <span>Memuat estimasi risiko cuaca wilayah...</span>
            </div>
          )}

          {!loadingRisk && riskData?.risk_level && (
            <div
              style={{
                backgroundColor: 'rgba(204, 111, 0, 0.08)',
                border: '1.5px solid rgba(204, 111, 0, 0.45)',
                borderRadius: '10px',
                padding: '12px 16px',
                marginBottom: '16px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>                <div>
                  <div style={{ fontSize: '11px', fontWeight: 700, color: '#CC6F00', textTransform: 'uppercase', letterSpacing: '0.04em', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <FlameIcon size={14} color="#CC6F00" />
                    Indikator Kerentanan Cuaca Sekitar (Eksperimental)
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--color-text-main)', marginTop: '2px' }}>
                    Indeks Kerentanan: <b style={{ color: '#CC6F00' }}>{riskData.risk_percentage}%</b>
                  </div>
                </div>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '4px 10px',
                    borderRadius: '6px',
                    fontSize: '11px',
                    fontWeight: 700,
                    backgroundColor:
                      riskData.risk_level === 'TINGGI'
                        ? 'rgba(239, 68, 68, 0.15)'
                        : riskData.risk_level === 'SEDANG'
                        ? 'rgba(234, 179, 8, 0.15)'
                        : riskData.risk_level === 'RENDAH'
                        ? 'rgba(34, 197, 94, 0.15)'
                        : 'rgba(156, 163, 175, 0.15)',
                    color:
                      riskData.risk_level === 'TINGGI'
                        ? '#ef4444'
                        : riskData.risk_level === 'SEDANG'
                        ? '#CC6F00'
                        : riskData.risk_level === 'RENDAH'
                        ? '#22c55e'
                        : '#6B7280',
                    border: `1px solid ${
                      riskData.risk_level === 'TINGGI'
                        ? '#ef4444'
                        : riskData.risk_level === 'SEDANG'
                        ? '#CC6F00'
                        : riskData.risk_level === 'RENDAH'
                        ? '#22c55e'
                        : '#9CA3AF'
                    }`,
                  }}
                >
                  <StatusPillDot
                    color={
                      riskData.risk_level === 'TINGGI'
                        ? '#ef4444'
                        : riskData.risk_level === 'SEDANG'
                        ? '#CC6F00'
                        : riskData.risk_level === 'RENDAH'
                        ? '#22c55e'
                        : '#6B7280'
                    }
                    size={7}
                  />
                  {riskData.risk_level === 'TIDAK_DAPAT_DINILAI'
                    ? 'TIDAK DAPAT DINILAI'
                    : `KERENTANAN ${riskData.risk_level}`}
                </span>
              </div>
              <div style={{ fontSize: '10px', color: 'var(--color-text-muted)', marginTop: '6px' }}>
                *Berdasarkan anomali mikroklimat satelit (bukan konfirmasi kepastian titik api darat).
              </div>
              {riskData.primary_drivers && riskData.primary_drivers.length > 0 && (
                <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px dashed rgba(204, 111, 0, 0.25)', fontSize: '11px', color: 'var(--color-text-muted)' }}>
                  <b>Deviasi Utama:</b>{' '}
                  {riskData.primary_drivers[0].label
                    .replace(/Suhu Udara Permukaan \(2m\)/i, 'Suhu Udara Permukaan')
                    .replace(/Kerapatan Kanopi/i, 'Kerapatan Tutupan Pohon')
                    .replace(/Elevasi Topografi \(Ketinggian\)/i, 'Ketinggian Wilayah')} ({riskData.primary_drivers[0].impact})
                </div>
              )}
            </div>
          )}

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
