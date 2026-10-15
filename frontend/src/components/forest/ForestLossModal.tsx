import React, { useEffect, useState } from 'react';
import type { ForestLossSummary } from '../../types/forest';
import { fetchForestLossSummary } from '../../services/api';

interface ForestLossModalProps {
  isOpen: boolean;
  onClose: () => void;
  isDark?: boolean;
}

export const ForestLossModal: React.FC<ForestLossModalProps> = ({
  isOpen,
  onClose,
  isDark = false,
}) => {
  const [data, setData] = useState<ForestLossSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedProvince, setSelectedProvince] = useState<string>('Semua');

  useEffect(() => {
    if (!isOpen) return;

    let isSubscribed = true;

    fetchForestLossSummary()
      .then((res) => {
        if (isSubscribed) {
          setData(res);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (isSubscribed) {
          setError(err instanceof Error ? err.message : 'Gagal memuat dataset tutupan pohon.');
          setIsLoading(false);
        }
      });

    return () => {
      isSubscribed = false;
    };
  }, [isOpen]);


  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!isOpen) return null;

  const formatHectares = (ha: number): string => {
    return new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 }).format(ha) + ' ha';
  };

  const formatMillionsHa = (ha: number): string => {
    return (ha / 1000000).toFixed(2) + ' Juta ha';
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="forest-loss-title"
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="modal-card"
        style={{
          maxWidth: '780px',
          maxHeight: '92vh',
          overflowY: 'auto',
          backgroundColor: isDark ? 'var(--color-bg-card, #1E293B)' : '#FFFFFF',
        }}
      >
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '20px' }}>🌲</span>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <h3 id="forest-loss-title" className="modal-title" style={{ margin: 0, fontSize: '15px' }}>
                  Analisis Perubahan Tutupan Pohon Kalimantan
                </h3>
                {data && (!data.data_verified || data.data_status) && (
                  <span
                    style={{
                      fontSize: '10px',
                      fontWeight: 600,
                      backgroundColor: 'rgba(245, 158, 11, 0.15)',
                      color: isDark ? '#FCD34D' : '#B45309',
                      border: '1px solid rgba(245, 158, 11, 0.4)',
                      padding: '1px 6px',
                      borderRadius: '4px',
                    }}
                  >
                    Data Demonstrasi (Belum Terverifikasi)
                  </span>
                )}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>
                Dataset Hansen Global Forest Change (UMD / Google / USGS / NASA) • Status: Data Demonstrasi
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Tutup modal analisis tutupan pohon"
            className="modal-close-btn"
          >
            ✕
          </button>
        </div>

        <div className="modal-body" style={{ padding: '16px' }}>
          {isLoading ? (
            <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--color-text-muted)' }}>
              <div style={{ fontSize: '24px', marginBottom: '8px' }}>⏳</div>
              <div>Memuat data spasial tutupan pohon Kalimantan (2000–2025)...</div>
            </div>
          ) : error ? (
            <div
              style={{
                padding: '16px',
                borderRadius: '6px',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid #EF4444',
                color: '#DC2626',
                fontSize: '13px',
              }}
            >
              ⚠️ {error}
            </div>
          ) : data ? (
            <>
              {/* Banner Transparansi Status Data Demonstrasi */}
              {(!data.data_verified || data.data_status) && (
                <div
                  style={{
                    padding: '10px 14px',
                    borderRadius: '6px',
                    backgroundColor: isDark ? 'rgba(245, 158, 11, 0.15)' : 'rgba(245, 158, 11, 0.08)',
                    border: '1px solid rgba(245, 158, 11, 0.4)',
                    marginBottom: '16px',
                    display: 'flex',
                    gap: '10px',
                    alignItems: 'flex-start',
                  }}
                >
                  <span style={{ fontSize: '18px', lineHeight: 1 }}>⚠️</span>
                  <div style={{ fontSize: '11px', lineHeight: 1.5, color: isDark ? '#FDE68A' : '#92400E' }}>
                    <div style={{ fontWeight: 700, marginBottom: '2px' }}>
                      Status Data: Data Demonstrasi (Belum Terverifikasi Raster)
                    </div>
                    <div>
                      {data.verification_notes ||
                        'Statistik tutupan pohon saat ini disajikan secara transparan sebagai data demonstrasi sementara dan belum melalui ingest raster GeoTIFF tingkat piksel terverifikasi.'}
                    </div>
                  </div>
                </div>
              )}

              {/* Ringkasan KPI Cards */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
                  gap: '10px',
                  marginBottom: '16px',
                }}
              >
                <div
                  style={{
                    padding: '12px',
                    borderRadius: '6px',
                    background: 'var(--color-bg-subtle, #F8FAFC)',
                    border: '1px solid var(--color-border, #E2E8F0)',
                  }}
                >
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>Baseline Tutupan 2000 (Demonstrasi)</div>
                  <div style={{ fontSize: '16px', fontWeight: 700, color: '#047857', marginTop: '2px' }}>
                    {formatMillionsHa(data.total_baseline_treecover_2000_ha)}
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--color-text-muted)' }}>Kanopi pohon &gt; 30%</div>
                </div>

                <div
                  style={{
                    padding: '12px',
                    borderRadius: '6px',
                    background: 'var(--color-bg-subtle, #F8FAFC)',
                    border: '1px solid var(--color-border, #E2E8F0)',
                  }}
                >
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>Akumulasi Kehilangan (Demonstrasi)</div>
                  <div style={{ fontSize: '16px', fontWeight: 700, color: '#DC2626', marginTop: '2px' }}>
                    {formatMillionsHa(data.total_cumulative_loss_2001_2025_ha)}
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--color-text-muted)' }}>Periode 2001–2025 ({data.total_percentage_lost}%)</div>
                </div>

                <div
                  style={{
                    padding: '12px',
                    borderRadius: '6px',
                    background: 'var(--color-bg-subtle, #F8FAFC)',
                    border: '1px solid var(--color-border, #E2E8F0)',
                  }}
                >
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>Cakupan Geografis</div>
                  <div style={{ fontSize: '14px', fontWeight: 700, color: '#0284C7', marginTop: '4px' }}>
                    5 Provinsi Kalimantan
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--color-text-muted)' }}>Indonesia (Eksklusif)</div>
                </div>

                <div
                  style={{
                    padding: '12px',
                    borderRadius: '6px',
                    background: 'var(--color-bg-subtle, #F8FAFC)',
                    border: '1px solid var(--color-border, #E2E8F0)',
                  }}
                >
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>Status & Versi Dataset</div>
                  <div style={{ fontSize: '13px', fontWeight: 700, color: '#D97706', marginTop: '4px' }}>
                    {data.data_status === 'demonstration' ? 'Data Demonstrasi' : (data.data_status || 'Demonstrasi')}
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--color-text-muted)' }}>Hansen GFC {data.last_updated}</div>
                </div>
              </div>

              {/* Pengecualian Wilayah Asing */}
              <div
                style={{
                  padding: '8px 12px',
                  borderRadius: '6px',
                  backgroundColor: 'rgba(59, 130, 246, 0.08)',
                  border: '1px solid rgba(59, 130, 246, 0.25)',
                  fontSize: '11px',
                  marginBottom: '16px',
                  lineHeight: 1.45,
                }}
              >
                🗺️ <b>Pengecualian Batas Geografis:</b> Analisis dibatasi ketat untuk 5 provinsi Kalimantan bagian Indonesia. Wilayah <b>Sarawak & Sabah (Malaysia)</b> serta <b>Brunei Darussalam</b> secara tegas dikecualikan dari cakupan data dan agregasi ini.
              </div>

              {/* Rincian per 5 Provinsi */}
              <div style={{ marginBottom: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-text-main)' }}>
                    Rincian per Provinsi Kalimantan (2000–2025){' '}
                    <span style={{ fontSize: '11px', fontWeight: 500, color: '#D97706' }}>
                      [Data Demonstrasi]
                    </span>
                  </span>
                  <select
                    aria-label="Pilih Provinsi"
                    value={selectedProvince}
                    onChange={(e) => setSelectedProvince(e.target.value)}
                    className="filter-select"
                    style={{ fontSize: '11px', padding: '3px 8px', height: '28px' }}
                  >
                    <option value="Semua">Semua 5 Provinsi</option>
                    {data.provincial_data.map((p) => (
                      <option key={p.province} value={p.province}>
                        {p.province}
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ overflowX: 'auto' }}>
                  <table
                    style={{
                      width: '100%',
                      borderCollapse: 'collapse',
                      fontSize: '11px',
                      textAlign: 'left',
                    }}
                  >
                    <thead>
                      <tr style={{ background: 'var(--color-bg-subtle, #F1F5F9)', borderBottom: '2px solid var(--color-border, #CBD5E1)' }}>
                        <th style={{ padding: '8px 10px' }}>Provinsi</th>
                        <th style={{ padding: '8px 10px', textAlign: 'right' }}>Baseline 2000</th>
                        <th style={{ padding: '8px 10px', textAlign: 'right' }}>Total Kehilangan (2001–2025)</th>
                        <th style={{ padding: '8px 10px', textAlign: 'right' }}>Persentase</th>
                        <th style={{ padding: '8px 10px', textAlign: 'right' }}>Kehilangan 2024–2025</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.provincial_data
                        .filter((p) => selectedProvince === 'Semua' || p.province === selectedProvince)
                        .map((prov) => (
                          <tr
                            key={prov.province}
                            style={{ borderBottom: '1px solid var(--color-border, #E2E8F0)' }}
                          >
                            <td style={{ padding: '8px 10px', fontWeight: 600 }}>{prov.province}</td>
                            <td style={{ padding: '8px 10px', textAlign: 'right' }}>{formatHectares(prov.baseline_treecover_2000_ha)}</td>
                            <td style={{ padding: '8px 10px', textAlign: 'right', color: '#DC2626', fontWeight: 600 }}>
                              {formatHectares(prov.cumulative_loss_2001_2025_ha)}
                            </td>
                            <td style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 600 }}>{prov.percentage_lost}%</td>
                            <td style={{ padding: '8px 10px', textAlign: 'right', color: '#B45309' }}>
                              {formatHectares(prov.recent_loss_2024_2025_ha)}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Metodologi Perhitungan Geodesik */}
              <div
                style={{
                  padding: '12px 14px',
                  borderRadius: '6px',
                  background: 'var(--color-bg-subtle, #F8FAFC)',
                  border: '1px solid var(--color-border, #E2E8F0)',
                  marginBottom: '16px',
                  fontSize: '11px',
                  lineHeight: 1.5,
                }}
              >
                <div style={{ fontWeight: 700, color: 'var(--color-text-main)', marginBottom: '4px' }}>
                  📐 Metode Perhitungan Luas Geospasial
                </div>
                <div>{data.methodology}</div>
                <div style={{ marginTop: '4px', fontStyle: 'italic', color: 'var(--color-text-muted)' }}>
                  Perhitungan mengoreksi konvergensi bujur terhadap garis lintang (kosinus lintang), sehingga estimasi luas piksel ~0.0953 ha/piksel di khatulistiwa merefleksikan geometri ellipsoida WGS84 secara akurat.
                </div>
              </div>

              {/* Keterbatasan Ilmiah Wajib */}
              <div
                style={{
                  padding: '12px 14px',
                  borderRadius: '6px',
                  backgroundColor: 'rgba(245, 158, 11, 0.08)',
                  border: '1px solid rgba(245, 158, 11, 0.3)',
                  marginBottom: '16px',
                }}
              >
                <div style={{ fontSize: '12px', fontWeight: 700, color: '#B45309', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span>⚠️</span> Peringatan Ilmiah & Definisi Dataset
                </div>
                <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '11px', color: 'var(--color-text-main)', lineHeight: 1.5 }}>
                  {data.limitations.map((lim, idx) => (
                    <li key={idx} style={{ marginBottom: '4px' }}>
                      {lim}
                    </li>
                  ))}
                </ul>
              </div>

              {/* Tautan Sumber Data */}
              <div style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>
                <b>Dokumentasi Resmi Dataset:</b>{' '}
                <a
                  href={data.documentation_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: '#0284C7', textDecoration: 'underline' }}
                >
                  developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2025_v1_13
                </a>
              </div>
            </>
          ) : null}
        </div>

        <div className="modal-footer" style={{ borderTop: '1px solid var(--color-border)' }}>
          <button
            type="button"
            onClick={onClose}
            className="btn-action"
            style={{ padding: '6px 14px', fontSize: '12px' }}
          >
            Tutup
          </button>
        </div>
      </div>
    </div>
  );
};
