import React, { useState } from 'react';
import type { CitizenReport, ReportCategory, EvidenceAssessmentLabel } from '../../types/report';
import { CATEGORY_LABELS, EVIDENCE_BADGE_CONFIG } from '../../types/report';
import {
  LeafIcon,
  FlameIcon,
  TractorIcon,
  TreeIcon,
  CameraIcon,
  AlertTriangleIcon,
  ZapIcon,
  SearchIcon,
  HourglassIcon,
} from '../common/SvgIcons';

interface ReportListProps {
  reports: CitizenReport[];
  onSelectReport: (report: CitizenReport) => void;
  selectedId?: string;
  onOpenCreateModal: () => void;
}

export const ReportList: React.FC<ReportListProps> = ({
  reports,
  onSelectReport,
  selectedId,
  onOpenCreateModal,
}) => {
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [evidenceFilter, setEvidenceFilter] = useState<string>('');

  const filteredReports = reports.filter((r) => {
    if (categoryFilter && r.category !== categoryFilter) return false;
    if (evidenceFilter) {
      const assessmentLabel = r.evidence_assessment?.category_result;
      if (assessmentLabel !== evidenceFilter) return false;
    }
    return true;
  });

  return (
    <div className="detection-list-wrapper report-list-container" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header List Laporan */}
      <div className="detection-list-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span className="detection-list-title">Laporan Partisipasi Warga</span>
          <span className="detection-list-meta" style={{ marginLeft: '6px' }}>{filteredReports.length} laporan</span>
        </div>
        <button
          type="button"
          onClick={onOpenCreateModal}
          className="btn-action"
          style={{
            fontSize: '11px',
            padding: '3px 8px',
            minHeight: '28px',
            background: 'var(--color-forest)',
            color: '#fff',
            fontWeight: 600,
          }}
        >
          + Buat Laporan
        </button>
      </div>

      {/* Filter Toolbar Cepat */}
      <div style={{ display: 'flex', gap: '6px', padding: '8px 10px', background: 'var(--color-bg-subtle)', borderBottom: '1px solid var(--color-border)' }}>
        <select
          aria-label="Filter Kategori"
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="filter-select"
          style={{ fontSize: '11px', padding: '3px 6px', height: '30px', flex: 1 }}
        >
          <option value="">Semua Kategori</option>
          <option value="kebakaran">Kebakaran / Asap</option>
          <option value="pembukaan_lahan">Pembukaan Lahan</option>
          <option value="perubahan_tutupan">Perubahan Tutupan</option>
        </select>

        <select
          aria-label="Filter Hasil Penilaian Bukti"
          value={evidenceFilter}
          onChange={(e) => setEvidenceFilter(e.target.value)}
          className="filter-select"
          style={{ fontSize: '11px', padding: '3px 6px', height: '30px', flex: 1 }}
        >
          <option value="">Semua Bukti</option>
          <option value="Ada indikasi pendukung">Ada Indikasi</option>
          <option value="Belum ditemukan kecocokan">Belum Cocok</option>
          <option value="Belum dapat dinilai">Belum Dinilai</option>
        </select>
      </div>

      {/* Konten Scroll List Laporan */}
      <div className="detection-items-scroll" style={{ flex: 1, overflowY: 'auto' }}>
        {filteredReports.length === 0 ? (
          <div style={{ padding: '24px 16px', textAlign: 'center', color: 'var(--color-text-muted)', fontSize: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '8px' }}>
              <LeafIcon size={28} color="#059669" />
            </div>
            <div style={{ fontWeight: 500 }}>Belum ada laporan warga pada filter ini.</div>
            <div style={{ fontSize: '11px', marginTop: '4px' }}>
              Masyarakat dapat melaporkan indikasi asap atau perubahan kondisi tutupan pohon di Kalimantan.
            </div>
            <button
              type="button"
              onClick={onOpenCreateModal}
              className="btn-action"
              style={{ marginTop: '12px', fontSize: '11px', padding: '6px 12px' }}
            >
              Kirim Laporan Pertama
            </button>
          </div>
        ) : (
          filteredReports.map((r) => {
            const isSelected = selectedId === r.id;
            const evidence = r.evidence_assessment;
            const assessmentLabel = (evidence?.category_result || 'Belum dapat dinilai') as EvidenceAssessmentLabel;
            const badge = EVIDENCE_BADGE_CONFIG[assessmentLabel] || EVIDENCE_BADGE_CONFIG['Belum dapat dinilai'];

            const renderBadgeIcon = () => {
              if (assessmentLabel === 'Ada indikasi pendukung') {
                return <ZapIcon size={11} color={badge.text} />;
              }
              if (assessmentLabel === 'Belum ditemukan kecocokan') {
                return <SearchIcon size={11} color={badge.text} />;
              }
              return <HourglassIcon size={11} color={badge.text} />;
            };

            const renderCategoryIcon = () => {
              if (r.category === 'kebakaran') {
                return <FlameIcon size={13} color="#CC6F00" />;
              }
              if (r.category === 'pembukaan_lahan') {
                return <TractorIcon size={13} color="#D97706" />;
              }
              return <TreeIcon size={13} color="#059669" />;
            };

            return (
              <button
                key={r.id}
                type="button"
                onClick={() => onSelectReport(r)}
                className={`detection-item-btn ${isSelected ? 'selected' : ''}`}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'stretch',
                  padding: '9px 12px',
                  gap: '4px',
                  textAlign: 'left',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '6px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-main)', display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                    {renderCategoryIcon()}
                    <span>{CATEGORY_LABELS[r.category as ReportCategory] || r.category}</span>
                  </span>
                  <span
                    style={{
                      fontSize: '10px',
                      fontWeight: 600,
                      padding: '2px 6px',
                      borderRadius: '4px',
                      whiteSpace: 'nowrap',
                      backgroundColor: badge.bg,
                      color: badge.text,
                      border: `1px solid ${badge.border}`,
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    {renderBadgeIcon()}
                    <span>{assessmentLabel}</span>
                  </span>
                </div>

                <div className="detection-coord font-mono" style={{ fontSize: '11px' }}>
                  {r.latitude.toFixed(3)}°, {r.longitude.toFixed(3)}°
                  {r.province && <span style={{ marginLeft: '6px', fontWeight: 'normal', opacity: 0.85 }}>• {r.province}</span>}
                </div>

                <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  "{r.description}"
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '2px', fontSize: '10px', color: 'var(--color-text-muted)' }}>
                  <span>{r.observed_at_utc.slice(0, 16).replace('T', ' ')} UTC</span>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    {r.photo_url && (
                      <span title="Ada foto bukti" style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                        <CameraIcon size={12} color="var(--color-text-muted)" />
                        <span>Foto</span>
                      </span>
                    )}
                    {r.is_duplicate_suspect && (
                      <span style={{ color: '#D97706', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '3px' }} title="Kemiripan area">
                        <AlertTriangleIcon size={12} color="#D97706" />
                        <span>Duplikat?</span>
                      </span>
                    )}
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>

      <div className="detection-list-footer">
        Platform informasi warga untuk memantau indikasi kebakaran dan tutupan pohon Kalimantan.
      </div>
    </div>
  );
};
