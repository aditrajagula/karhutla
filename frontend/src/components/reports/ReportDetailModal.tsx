import React, { useEffect, useState } from 'react';
import type { CitizenReport, ReportStatus } from '../../types/report';
import { CATEGORY_LABELS, STATUS_LABELS, EVIDENCE_BADGE_CONFIG } from '../../types/report';
import { BACKEND_ORIGIN, fetchFireRiskPrediction, updateReportStatus } from '../../services/api';
import { isPetugas } from '../../services/dummyAuth';
import {
  CloseIcon,
  AlertTriangleIcon,
  CheckCircleIcon,
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
  TreeIcon,
} from '../common/SvgIcons';

interface ReportDetailModalProps {
  report: CitizenReport | null;
  onClose: () => void;
  onReportUpdated?: (updated: CitizenReport) => void;
}

export const ReportDetailModal: React.FC<ReportDetailModalProps> = ({
  report,
  onClose,
  onReportUpdated,
}) => {
  const canVerify = isPetugas();
  const [riskData, setRiskData] = useState<any>(report?.environmental_risk || null);
  const [loadingRisk, setLoadingRisk] = useState<boolean>(false);

  // State untuk form verifikasi petugas
  const [verifyStatus, setVerifyStatus] = useState<ReportStatus>(report?.status || 'IN_REVIEW');
  const [verifyNotes, setVerifyNotes] = useState<string>(report?.verification_notes || '');
  const [rejectReason, setRejectReason] = useState<string>(report?.rejection_reason || '');
  const [isUpdatingStatus, setIsUpdatingStatus] = useState<boolean>(false);
  const [verifyFeedback, setVerifyFeedback] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    if (report) {
      setVerifyStatus(report.status === 'PENDING' ? 'VERIFIED' : report.status);
      setVerifyNotes(report.verification_notes || '');
      setRejectReason(report.rejection_reason || '');
      setVerifyFeedback(null);
    }
  }, [report?.id, report?.status, report?.verification_notes, report?.rejection_reason]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    // Pada sesi petugas, panel risiko cuaca diabaikan
    if (!report || canVerify) return;

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
  }, [report?.id, report?.latitude, report?.longitude, report?.province, report?.environmental_risk, canVerify]);

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
    ? (report.photo_url.startsWith('http') ? report.photo_url : `${BACKEND_ORIGIN}${report.photo_url}`)
    : null;

  const handleSaveVerification = async (e: React.FormEvent) => {
    e.preventDefault();
    setVerifyFeedback(null);

    if (verifyStatus === 'REJECTED' && !rejectReason.trim()) {
      setVerifyFeedback({
        type: 'error',
        text: 'Alasan penolakan wajib diisi jika laporan ditolak.',
      });
      return;
    }

    setIsUpdatingStatus(true);
    try {
      const res = await updateReportStatus(report.id, {
        status: verifyStatus,
        verification_notes: verifyNotes.trim() || null,
        rejection_reason: verifyStatus === 'REJECTED' ? rejectReason.trim() : null,
      });
      setVerifyFeedback({
        type: 'success',
        text: res.message || `Status laporan berhasil diperbarui menjadi ${STATUS_LABELS[verifyStatus]}.`,
      });
      if (onReportUpdated && res.data) {
        onReportUpdated(res.data);
      }
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Gagal memperbarui status verifikasi.';
      setVerifyFeedback({ type: 'error', text: msg });
    } finally {
      setIsUpdatingStatus(false);
    }
  };

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
            <TreeIcon size={18} color="#059669" />
            <h3 id="report-detail-title" className="modal-title">
              Detail Laporan Deforestasi & Penilaian Bukti
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
                Hasil Penilaian Bukti Tutupan Hutan & Deforestasi
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
                {report.category !== 'kebakaran' && (Boolean(evidence.details['dataset']) || Boolean(evidence.details['forest_extent_2020'])) && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <BookIcon size={13} color="var(--color-text-muted)" />
                      <span><b>Dataset Evaluasi:</b> Hansen GFC 2025 v1.13</span>
                    </div>
                    {Boolean(evidence.details['forest_extent_2020']) && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <TreeIcon size={13} color="#059669" />
                        <span>
                          <b>Klasifikasi Tutupan Hutan:</b>{' '}
                          {(evidence.details['forest_extent_2020'] as any)?.classification === 'FOREST'
                            ? 'Hutan Kanopi >= 5m (Terkonfirmasi)'
                            : (evidence.details['forest_extent_2020'] as any)?.classification === 'NON_FOREST'
                            ? 'Bukan Hutan'
                            : 'Di Luar Cakupan Raster'}
                        </span>
                      </div>
                    )}
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

          {/* PANEL ESTIMASI RISIKO KEBAKARAN (Hanya untuk pelapor/warga jika data tersedia, disembunyikan pada sesi petugas) */}
          {!canVerify && loadingRisk && (
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

          {!canVerify && !loadingRisk && riskData?.risk_level && riskData.risk_level !== 'TIDAK_DAPAT_DINILAI' && (
            <div
              style={{
                backgroundColor: 'rgba(204, 111, 0, 0.08)',
                border: '1.5px solid rgba(204, 111, 0, 0.45)',
                borderRadius: '10px',
                padding: '12px 16px',
                marginBottom: '16px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ fontSize: '11px', fontWeight: 700, color: '#CC6F00', textTransform: 'uppercase', letterSpacing: '0.04em', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <FlameIcon size={14} color="#CC6F00" />
                    Indikator Kerentanan Cuaca Sekitar (Eksperimental)
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--color-text-main)', marginTop: '2px' }}>
                    Indeks Kerentanan: <b style={{ color: '#CC6F00' }}>{riskData.risk_percentage ?? 0}%</b>
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
                  {`KERENTANAN ${riskData.risk_level}`}
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

          {/* Catatan Hasil Verifikasi Petugas (Terlihat oleh Warga & Petugas) */}
          {(report.verification_notes || report.rejection_reason) && (
            <div
              style={{
                marginTop: '14px',
                padding: '12px 14px',
                borderRadius: '8px',
                backgroundColor: currentTheme.bg,
                border: `1px solid ${currentTheme.border}`,
                fontSize: '12px',
                lineHeight: 1.5,
              }}
            >
              <div style={{ fontWeight: 700, color: currentTheme.text, marginBottom: '4px' }}>
                Hasil Tinjauan Petugas ({STATUS_LABELS[report.status]}):
              </div>
              {report.verification_notes && (
                <div style={{ color: 'var(--color-text-main)' }}>
                  <b>Catatan Petugas:</b> {report.verification_notes}
                </div>
              )}
              {report.rejection_reason && (
                <div style={{ color: '#DC2626', marginTop: '4px' }}>
                  <b>Alasan Penolakan:</b> {report.rejection_reason}
                </div>
              )}
              {report.status === 'REJECTED' && (
                <div style={{ color: '#DC2626', marginTop: '6px', fontSize: '11px' }}>
                  📌 <i>Titik penanda laporan ini telah ditiadakan dari peta interaktif.</i>
                </div>
              )}
            </div>
          )}

          {/* Panel Tindakan Verifikasi Khusus Petugas */}
          {canVerify && (
            <form
              onSubmit={handleSaveVerification}
              style={{
                marginTop: '18px',
                padding: '14px 16px',
                borderRadius: '8px',
                backgroundColor: 'var(--color-bg-subtle)',
                border: '1.5px solid rgba(204, 111, 0, 0.5)',
              }}
            >
              <div
                style={{
                  fontSize: '12px',
                  fontWeight: 700,
                  color: '#CC6F00',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                  marginBottom: '10px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <CheckCircleIcon size={15} color="#CC6F00" />
                <span>Panel Verifikasi Petugas</span>
              </div>

              {verifyFeedback && (
                <div
                  style={{
                    padding: '8px 10px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    marginBottom: '10px',
                    backgroundColor:
                      verifyFeedback.type === 'success'
                        ? 'rgba(16, 185, 129, 0.15)'
                        : 'rgba(239, 68, 68, 0.15)',
                    border: `1px solid ${
                      verifyFeedback.type === 'success' ? '#059669' : '#DC2626'
                    }`,
                    color: verifyFeedback.type === 'success' ? '#059669' : '#DC2626',
                  }}
                >
                  {verifyFeedback.text}
                </div>
              )}

              <div style={{ marginBottom: '10px' }}>
                <label
                  htmlFor="verify-status-select"
                  style={{ display: 'block', fontSize: '11px', fontWeight: 600, marginBottom: '4px' }}
                >
                  Keputusan Status Verifikasi:
                </label>
                <select
                  id="verify-status-select"
                  value={verifyStatus}
                  onChange={(e) => setVerifyStatus(e.target.value as ReportStatus)}
                  className="filter-select"
                  style={{ width: '100%', fontSize: '12px', padding: '6px 8px' }}
                >
                  <option value="VERIFIED">Terverifikasi (VERIFIED)</option>
                  <option value="IN_REVIEW">Perlu Pemeriksaan Lebih Lanjut (IN_REVIEW)</option>
                  <option value="REJECTED">Ditolak dengan Alasan (REJECTED)</option>
                  <option value="PENDING">Menunggu Verifikasi (PENDING)</option>
                </select>
              </div>

              <div style={{ marginBottom: '10px' }}>
                <label
                  htmlFor="verify-notes-input"
                  style={{ display: 'block', fontSize: '11px', fontWeight: 600, marginBottom: '4px' }}
                >
                  Catatan Verifikasi Petugas:
                </label>
                <textarea
                  id="verify-notes-input"
                  rows={2}
                  value={verifyNotes}
                  onChange={(e) => setVerifyNotes(e.target.value)}
                  placeholder="Contoh: Sesuai pantauan satelit VIIRS dan laporan tim posko lapangan..."
                  className="filter-input"
                  style={{ width: '100%', fontSize: '12px', resize: 'vertical' }}
                />
              </div>

              {verifyStatus === 'REJECTED' && (
                <div style={{ marginBottom: '10px' }}>
                  <div
                    style={{
                      fontSize: '11px',
                      color: '#B91C1C',
                      background: 'rgba(239, 68, 68, 0.1)',
                      border: '1px solid rgba(239, 68, 68, 0.3)',
                      padding: '6px 8px',
                      borderRadius: '4px',
                      marginBottom: '8px',
                      lineHeight: 1.4,
                    }}
                  >
                    ℹ️ <b>Info:</b> Titik penanda laporan ini akan otomatis dihapus dari peta interaktif jika status ditolak / dibatalkan.
                  </div>
                  <label
                    htmlFor="reject-reason-input"
                    style={{ display: 'block', fontSize: '11px', fontWeight: 600, marginBottom: '4px', color: '#DC2626' }}
                  >
                    Alasan Penolakan (Wajib Diisi) *
                  </label>
                  <textarea
                    id="reject-reason-input"
                    rows={2}
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                    placeholder="Jelaskan alasan penolakan laporan ini..."
                    className="filter-input"
                    style={{ width: '100%', fontSize: '12px', resize: 'vertical', borderColor: '#DC2626' }}
                    required
                  />
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <button
                  type="submit"
                  disabled={isUpdatingStatus}
                  className="btn-action"
                  style={{
                    background: '#CC6F00',
                    color: '#fff',
                    fontWeight: 600,
                    fontSize: '12px',
                    padding: '6px 14px',
                    border: 'none',
                  }}
                >
                  {isUpdatingStatus ? 'Menyimpan...' : 'Simpan Status Verifikasi'}
                </button>
              </div>
            </form>
          )}
        </div>

        <div className="modal-footer">
          <p className="disclaimer-text">
            Platform JagaBorneo memadukan laporan partisipatif warga dengan penginderaan jauh satelit serta verifikasi bertahap oleh petugas.
          </p>
        </div>
      </div>
    </div>
  );
};

